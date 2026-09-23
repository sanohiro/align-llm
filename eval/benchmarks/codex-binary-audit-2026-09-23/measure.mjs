import fs from 'node:fs';
import path from 'node:path';
import {spawnSync} from 'node:child_process';

const [directory, output] = process.argv.slice(2);
if (!directory || !output || fs.existsSync(output)) {
  throw new Error('usage: node measure.mjs ARTIFACT_DIRECTORY NEW_OUTPUT.json');
}
const samples = [];
for (const benchmark of ['scan', 'greedy', 'sampler']) {
  for (let pair = 0; pair < 7; ++pair) {
    const order = pair % 2 === 0 ? ['old', 'new'] : ['new', 'old'];
    for (const [position, arm] of order.entries()) {
      const binary = benchmark === 'scan'
        ? path.join(directory, 'scan-' + arm)
        : path.join(directory, arm + '-bench', 'runtime_' + benchmark + '_bench');
      const run = spawnSync(binary, [], {encoding:'utf8', timeout:60000});
      if (run.error || run.status !== 0) {
        throw new Error(binary + ': ' + (run.error || run.stderr || run.signal));
      }
      let result;
      if (benchmark === 'scan') {
        result = JSON.parse(run.stdout);
        if (result.bytes !== 1048576 || result.iterations !== 2000 || result.observed !== 2020
            || !run.stderr.includes('PASS: 33153 zero/nonzero cases')) {
          throw new Error('invalid scan evidence');
        }
      } else {
        const found = run.stdout.match(/\n(\d+)\n us\/call/);
        if (!found) throw new Error('unrecognized benchmark output: ' + run.stdout);
        result = {us_per_call:Number(found[1])};
      }
      samples.push({benchmark,pair,position,arm,...result});
    }
  }
}
const median = values => [...values].sort((a,b)=>a-b)[Math.floor(values.length/2)];
const summaries = Object.fromEntries(['scan','greedy','sampler'].map(benchmark=>{
  const metric = benchmark === 'scan' ? 'gb_per_s' : 'us_per_call';
  return [benchmark, {metric, ...Object.fromEntries(['old','new'].map(arm=>[
    arm, median(samples.filter(x=>x.benchmark===benchmark && x.arm===arm).map(x=>x[metric]))
  ]))}];
}));
fs.writeFileSync(output, JSON.stringify({pairs:7,samples,summaries},null,2)+'\n', {flag:'wx'});
console.log(JSON.stringify(summaries,null,2));
