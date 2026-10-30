import test from 'node:test';
import assert from 'node:assert/strict';
import {importJob} from '../plugins/browser-to-pages/skills/browser-to-pages/scripts/import-job.mjs';

function fixture({fail=false}={}) {
  let job={title:'Example',page_id:'example-page',parent_page_id:'example-parent',state:'prepared',
    units:['```javascript\n    const x = 1;\n```','{{IMAGE0}}','{{IMAGE1}}'],
    images:[{sha256:'first',path:'first.gif'},{sha256:'second',path:'second.gif'}],uploads:{}};
  let blocks=[],active=0,maxActive=0,uploads=0,edits=0;
  const adapter={
    loadJob:async()=>structuredClone(job),
    checkpoint:async patch=>{
      job={...job,...patch,uploads:{...job.uploads,...patch.uploads}}; return structuredClone(job);
    },
    finalize:async()=>job.units.map(u=>u.replace(/\{\{IMAGE(\d+)\}\}/g,(_,i)=>{
      const receipt=job.uploads[job.images[Number(i)].sha256];
      if(!receipt?.file_access_confirmed) throw Error('unconfirmed'); return receipt.markdown;
    })),
    readPage:async()=>({structuredContent:{content:{page_id:job.page_id,title:job.title,blocks},metadata:{parent:{page_id:job.parent_page_id}}}}),
    uploadImage:async ({file,page_id})=>{
      uploads++;active++;maxActive=Math.max(maxActive,active);
      await new Promise(r=>setTimeout(r,5));active--;
      if(fail&&file==='second.gif')return {isError:true};
      return {structuredContent:{page_id,sha256:file==='first.gif'?'first':'second',file_access_confirmed:true,markdown:`![image](library-file:${file})`}};
    },
    editPage:async ({operations})=>{
      edits++;blocks=operations[0].block_units.map(markdown=>({markdown}));
      return {structuredContent:{operation_results:[{status:'applied'}]}};
    }
  };
  return {adapter,state:()=>({job,blocks,maxActive,uploads,edits}),change:()=>{blocks[0].markdown='User edit';}};
}

test('bounded concurrent uploads, code preservation and idempotent resume',async()=>{
  const f=fixture(); const result=await importJob(f.adapter,{concurrency:2});
  assert.equal(result.state,'complete');assert.equal(f.state().maxActive,2);
  assert.equal(f.state().blocks[0].markdown,'```javascript\n    const x = 1;\n```');
  assert.equal((await importJob(f.adapter)).skipped,true);
  assert.equal(f.state().uploads,2);assert.equal(f.state().edits,1);
  f.change();await assert.rejects(()=>importJob(f.adapter),/differs/);
  assert.equal(f.state().job.state,'conflict');assert.equal(f.state().edits,1);
});

test('retain successful siblings and do not retry uncertain uploads',async()=>{
  const f=fixture({fail:true});
  await assert.rejects(()=>importJob(f.adapter,{concurrency:2}),/outcome uncertain/);
  assert.equal(Object.keys(f.state().job.uploads).length,1);
  assert.equal(f.state().edits,0);assert.equal(f.state().job.state,'upload_unknown');
  await assert.rejects(()=>importJob(f.adapter),/Reconcile/);
  assert.equal(f.state().uploads,2);
});
