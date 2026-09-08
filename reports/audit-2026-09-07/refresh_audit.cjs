// Read-only audit of implementation inputs; writes only this audit's evidence.
const fs = require('fs');
const path = require('path');
const cp = require('child_process');
const crypto = require('crypto');
const root = path.resolve(__dirname, '../..');
const hash = b => crypto.createHash('sha256').update(b).digest('hex');
const out = path.join(__dirname, 'refresh-evidence');
fs.mkdirSync(out, { recursive: true });
function inventory() {
  const listed = cp.execFileSync('git', ['ls-files', '--cached', '--others', '--exclude-standard', '-z'], { cwd: root, encoding: 'utf8', maxBuffer: 16e6 }).split('\0').filter(Boolean);
  const unique = [...new Set(listed)].sort();
  const files = unique.map(p => {
    try { const s = fs.statSync(path.join(root, p)); return { path: p, bytes: s.size }; }
    catch { return { path: p, missing: true }; }
  });
  const statePath = path.join(root, '.mister/state.json');
  const state = JSON.parse(fs.readFileSync(statePath));
  const candidatePath = state.candidate?.development_manifest || '.mister/evidence/candidates/fpga-candidate-20260907-9-arm.json';
  const candidate = JSON.parse(fs.readFileSync(path.join(root, candidatePath)));
  const inspect = list => list.map(f => {
    try { const h = hash(fs.readFileSync(path.join(root, f.path))); return { path: f.path, expected: f.sha256, actual: h, matches: h === f.sha256 }; }
    catch (e) { return { path: f.path, error: e.message, matches: false }; }
  });
  const sources = inspect(candidate.inputs.source_files);
  const artifacts = inspect(candidate.artifacts);
  const result = { timestamp: new Date().toISOString(), candidatePath, candidate_id: candidate.candidate_id,
    git_head: cp.execFileSync('git', ['rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8' }).trim(),
    git_status: cp.execFileSync('git', ['status', '--porcelain=v1', '--untracked-files=all'], { cwd: root, encoding: 'utf8', maxBuffer: 16e6 }),
    files, source_comparison: sources, artifact_comparison: artifacts };
  fs.writeFileSync(path.join(out, 'inventory.json'), JSON.stringify(result, null, 2) + '\n');
  console.log(JSON.stringify({ files: files.length, sources: sources.length, changed_sources: sources.filter(x => !x.matches).map(x => x.path), artifacts_match: artifacts.every(x => x.matches) }));
}
function launch(optional = false) {
  const log = fs.openSync(path.join(out, 'local-verification.log'), 'a');
  const code = optional
    ? "const fs=require('fs'),cp=require('child_process');const root=process.argv[1];const j=JSON.parse(fs.readFileSync(root+'/.mister/evidence/receipts/20260907T070202Z-696eb1c8-c7eb-4f48-bb87-a82772780688.json'));const checks=[];for(const step of j.results.filter(x=>['host-png','transport-sdl-input'].includes(x.id))){for(const cmd of step.commands){const r=cp.spawnSync(cmd[0],cmd.slice(1),{cwd:root,encoding:'utf8',timeout:180000,maxBuffer:16000000,windowsHide:true});const log='reports/audit-2026-09-07/refresh-evidence/'+step.id+'.log';fs.writeFileSync(root+'/'+log,(r.stdout||'')+(r.stderr||''));checks.push({id:step.id,command:cmd,exit_code:r.status,error:r.error?.message,log});fs.writeFileSync(process.argv[2],JSON.stringify(checks,null,2));}}"
    : "const fs=require('fs'),cp=require('child_process');const r=cp.spawnSync('python',['support/scripts/diablo.py','verify','--suite','local'],{cwd:process.argv[1],encoding:'utf8',timeout:900000,maxBuffer:16000000,windowsHide:true});fs.writeFileSync(process.argv[2],JSON.stringify({status:r.status,error:r.error?.message,stdout:r.stdout,stderr:r.stderr},null,2));";
  const child = cp.spawn(process.execPath, ['-e', code, root, path.join(out, optional ? 'optional-checks.json' : 'local-verification-result.json')], { cwd: root, detached: true, windowsHide: true, stdio: ['ignore', log, log] });
  child.unref(); fs.closeSync(log); console.log('Verification started; PID ' + child.pid);
}
if (process.argv[2] === 'launch') launch(); else if (process.argv[2] === 'optional') launch(true); else inventory();
