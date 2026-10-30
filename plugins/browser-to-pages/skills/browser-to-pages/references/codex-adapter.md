# Optional Codex adapter

Use only when the active tool catalog actually supplies Code Mode, shell execution and Pages tools. Resolve all paths from the current task and installed package, not a hardcoded user directory.

Map the engine's `readPage`, `uploadImage` and `editPage` functions to the current normalized Pages tool methods after reading their active schemas. Invoke the Python helper through `exec_command` for `loadJob`, `checkpoint`, and `finalize`:

```javascript
const quote = value => "'" + String(value).replace(/'/g, "'\\''") + "'";
async function jobOperation(command, patch) {
  let cmd = ['python3', helperPath, command, '--job', jobPath].map(quote).join(' ');
  if (patch) cmd += ' --patch ' + quote(JSON.stringify(patch));
  const result = await tools.exec_command({cmd, max_output_tokens:30000});
  if (result.exit_code !== 0) throw Error(result.output);
  return JSON.parse(result.output);
}
```

The adapter uses shell quoting rather than interpolating `JSON.stringify()` as executable shell text. For large jobs verify output completeness instead of parsing truncated JSON. Load trusted bundled engine source through the host's supported module/evaluation mechanism, never evaluate captured page HTML or JavaScript. Use current-host attachment file paths. Persist each batch and retain unknown-outcome markers.
