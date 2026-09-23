import fs from 'node:fs';
const [input, output] = process.argv.slice(2);
function decode(name) {
  const m = name.match(/^_?align_fn\$(\d+)\$([0-9a-f]+)$/);
  if (!m) return null;
  const b = Buffer.from(m[2], 'hex');
  if (b.length !== Number(m[1])) throw new Error('invalid encoded symbol: ' + name);
  return b.toString('utf8');
}
const functions = [];
let current = null;
for (const line of fs.readFileSync(input, 'utf8').split('\n')) {
  const header = line.match(/^([0-9a-f]+) <([^>]+)>:$/);
  if (header) {
    current = {address:parseInt(header[1],16),symbol:header[2],name:decode(header[2]),instructions:[]};
    functions.push(current);
  } else {
    const ins = line.match(/^\s*([0-9a-f]+):\s+(\S+)(?:\s+(.*))?$/);
    if (ins && current) current.instructions.push({address:parseInt(ins[1],16),op:ins[2],args:ins[3]||''});
  }
}
const byAddress = new Map(functions.map(f=>[f.address,f]));
const aligns = functions.filter(f=>f.name);
const callers = new Map();
const runtimeCalls = new Map();
const clamps = [];
const fp = [];
const tail = [];
for (const f of aligns) for (const ins of f.instructions) {
  if (ins.op === 'bl' || ins.op === 'b') {
    const addr = ins.args.match(/^0x([0-9a-f]+)/);
    const dest = addr && byAddress.get(parseInt(addr[1],16));
    if (dest?.name && ins.address !== dest.address) {
      const row={caller:f.name,target:dest.name,address:ins.address,instructions:dest.instructions.length};
      if(ins.op==='b') tail.push(row);
      else {const list=callers.get(dest.name)||[];list.push(row);callers.set(dest.name,list);}
    }
    const runtime = ins.args.match(/<(_align_rt_[^>+]+)>/);
    if (runtime && ins.op === 'bl') runtimeCalls.set(runtime[1],(runtimeCalls.get(runtime[1])||0)+1);
  }
  const clamp = ins.op==='bic' && ins.args.match(/^(x\d+), (x\d+), (x\d+), asr #(?:0x3f|63)$/);
  if(clamp && clamp[2]===clamp[3]) clamps.push({function:f.name,...ins});
  if (/^f(?:add|sub|mul|div|mla|mls|max|min|sqrt|abd|neg|abs|cmeq|cmgt|cmge|recpe|rsqrte|addp|addv)/.test(ins.op)
      && (/\.[248](?:s|d|h)$/.test(ins.op) || /\bv\d+\.[248](?:s|d|h)\b/.test(ins.args))) fp.push({function:f.name,...ins});
}
const small=aligns.filter(f=>f.instructions.length<=8);
const shortCalls=small.flatMap(f=>callers.get(f.name)||[]);
const targets=[...callers.entries()].map(([name,calls])=>({name,count:calls.length,instructions:calls[0].instructions})).sort((a,b)=>b.count-a.count);
const report={
  definitions:aligns.length,smallDefinitions:small.length,shortDirectCalls:shortCalls.length,
  shortTargets:targets.filter(x=>x.instructions<=8),allTargets:targets,
  tailCallsToSmall:tail.filter(x=>x.instructions<=8),lengthClamps:clamps,
  floatingSimdInstructions:fp.length,floatingSimdFunctions:[...new Set(fp.map(x=>x.function))],
  runtimeCalls:[...runtimeCalls].sort((a,b)=>b[1]-a[1]),
  named:Object.fromEntries(['ggml_ffi$handle_absent','runtime_attention$fused','runtime_attention$cached_f16','kv_plane$all_zero'].map(name=>[name,{
    calls:(callers.get(name)||[]).length,body:aligns.find(x=>x.name===name)?.instructions||[]
  }]))
};
fs.writeFileSync(output,JSON.stringify(report,null,2)+'\n');
fs.writeFileSync(output+'.functions.json',JSON.stringify(aligns,null,2)+'\n');
console.log(JSON.stringify({definitions:report.definitions,smallDefinitions:report.smallDefinitions,shortDirectCalls:report.shortDirectCalls,
  clamps:clamps.length,floatingSimdInstructions:fp.length,shortTargets:report.shortTargets.slice(0,18)},null,2));
