/** Host-neutral importer: inject job storage and the current Pages tool adapter. */
export async function importJob(adapter, {concurrency=4, notify=()=>{}}={}) {
  async function helper(command, patch) {
    if (command === 'show') return adapter.loadJob();
    if (command === 'checkpoint') return adapter.checkpoint(patch);
    if (command === 'finalize') return adapter.finalize();
    throw new Error('Unknown job operation');
  }
  function data(r) {
    if (r.isError || r.structuredContent?.error || !r.structuredContent)
      throw new Error('Pages call requires reconciliation: ' + JSON.stringify(r));
    return r.structuredContent;
  }
  let job = await helper('show');
  if (!job.page_id || !job.parent_page_id) throw new Error('Resolve/create destination and checkpoint its Page/parent IDs first');
  if (['create_unknown','upload_unknown','edit_unknown','conflict'].includes(job.state))
    throw new Error('Reconcile the recorded uncertain outcome before resuming');
  const read = () => adapter.readPage({page_id:job.page_id, view:'full'}).then(data);
  let p = await read();
  if (p.content.page_id !== job.page_id || p.metadata.parent?.page_id !== job.parent_page_id)
    throw new Error('Destination identity/parent changed');
  if (p.content.title !== job.title || (job.state === 'complete' && !p.content.blocks.length)) {
    await helper('checkpoint', {state:'conflict'});
    throw new Error('Managed Page was renamed or emptied; preserve the user change');
  }
  if (p.content.blocks.length) {
    const expected = await helper('finalize');
    if (p.content.title === job.title && p.content.blocks.length === expected.length &&
        p.content.blocks.every((b,i) => b.markdown === expected[i])) {
      await helper('checkpoint', {state:'complete'});
      notify?.({title:job.title, state:'complete', skipped:true});
      return {page_id:job.page_id, state:'complete', skipped:true, uploads:0};
    }
    await helper('checkpoint', {state:'conflict'});
    throw new Error('Existing content differs; preserve user edits and reconcile');
  }
  const unique = [...new Map(job.images.map(i => [i.sha256,i])).values()];
  const pending = unique.filter(i => {
    const u=job.uploads[i.sha256];
    return !(u?.file_access_confirmed && u.markdown && u.page_id === job.page_id);
  });
  const width = Math.max(1, Math.min(8, concurrency));
  for (let start=0; start<pending.length; start+=width) {
    const batch=pending.slice(start,start+width);
    const results=await Promise.allSettled(batch.map(i =>
      adapter.uploadImage({
        page_id:job.page_id, file:i.path, title:job.title+' '+(i.alt || '配图')
      })));
    const uploads={}; const uncertain=[];
    results.forEach((r,i) => {
      const result=r.status==='fulfilled' ? r.value : {error:String(r.reason)};
      const u=result.structuredContent;
      if (!result.isError && u?.file_access_confirmed && u.markdown &&
          u.sha256===batch[i].sha256 && u.page_id===job.page_id) uploads[batch[i].sha256]=u;
      else uncertain.push({sha256:batch[i].sha256, result});
    });
    job=await helper('checkpoint', {uploads, state:uncertain.length?'upload_unknown':'uploading', uncertain});
    notify?.({title:job.title, confirmed:Object.keys(job.uploads).length, total:unique.length});
    if (uncertain.length) throw new Error('Upload outcome uncertain; confirmed siblings checkpointed. Inspect Files before retrying.');
  }
  const units=await helper('finalize');
  const size=new TextEncoder().encode(JSON.stringify(units)).length;
  if (size>240000) throw new Error('Check actual UTF-8 payload against current Pages limits before committing a large chapter');
  p=await read();
  if (p.content.blocks.length || p.content.title!==job.title || p.metadata.parent?.page_id!==job.parent_page_id) throw new Error('Page changed during uploads; reconcile instead of overwriting');
  await helper('checkpoint', {state:'edit_unknown'});
  const args={page_id:p.content.page_id, operations:[{
    op:'insert_markdown', at:{kind:'between_blocks',preceding_block_id:null,following_block_id:null}, block_units:units
  }]};
  if (p.content.through_sequence !== undefined) args.base_sequence=p.content.through_sequence;
  const receipt=data(await adapter.editPage(args));
  if (!receipt.operation_results?.length || receipt.operation_results.some(o =>
      o.status==='rejected' || o.ignored_reason || o.error_code))
    throw new Error('Page edit needs reconciliation; do not replay');
  const actual=await read();
  if (actual.content.title!==job.title || actual.content.blocks.length!==units.length ||
      actual.content.blocks.some((b,i)=>b.markdown!==units[i]))
    throw new Error('Read-back differs; inspect canonical formatting before retrying');
  await helper('checkpoint', {state:'complete'});
  notify?.({title:job.title,state:'complete',blocks:units.length});
  return {page_id:job.page_id,state:'complete',skipped:false,uploads:pending.length};
}
