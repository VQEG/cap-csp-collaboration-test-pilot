#!/usr/bin/env node
// Player process: one JSON message per line on stdin, one reply per line on stdout.
// Adapted from scripts/network_js_worker.mjs in SFV-VQEG-CAP-CSP-Collaboration-Experiments v0.7.2
// by Michael Seufert: https://github.com/micseu/SFV-VQEG-CAP-CSP-Collaboration-Experiments/blob/9d7d6f9/scripts/network_js_worker.mjs
import readline from 'node:readline';
import { NetworkStepHarness } from './network_step_harness.js';

const input = readline.createInterface({ input: process.stdin, crlfDelay: Infinity });
let harness;
for await (const line of input) {
  try {
    const message = JSON.parse(line);
    let reply;
    if (message.type === 'initialize') {
      if (harness) throw new Error('Player already initialized');
      harness = new NetworkStepHarness(message.config);
      reply = {type: 'initialized'};
    } else if (!harness) throw new Error('Player not initialized');
    else if (message.type === 'network_step') reply = harness.onStep(message.step);
    else if (message.type === 'cap_reports') reply = {type: 'cap_reports', reports: harness.getCapReports()};
    else throw new Error(`Unknown IPC message ${message.type}`);
    process.stdout.write(JSON.stringify(reply) + '\n');
  } catch (error) {
    process.stdout.write(JSON.stringify({type: 'error', message: String(error.message ?? error)}) + '\n');
  }
}
