// Exercise beads-ui websocket write path directly (no browser).
// Sends add-comment then update-status closed for the question ticket.
import WebSocket from './node_modules/ws/index.js';

const ws = new WebSocket('ws://127.0.0.1:3000/ws');
const pending = new Map();
let seq = 0;

function send(type, payload) {
  return new Promise((resolve) => {
    const id = `req-${++seq}`;
    pending.set(id, resolve);
    ws.send(JSON.stringify({ id, type, payload }));
  });
}

ws.on('message', (data) => {
  const msg = JSON.parse(data.toString());
  if (msg.id && pending.has(msg.id)) {
    pending.get(msg.id)(msg);
    pending.delete(msg.id);
  }
});

ws.on('open', async () => {
  const c = await send('add-comment', {
    id: 'beads-board-orq',
    text: 'Answer: pixel art. Matches the retro look we locked in.'
  });
  console.log('add-comment reply:', JSON.stringify(c).slice(0, 300));
  const s = await send('update-status', { id: 'beads-board-orq', status: 'closed' });
  console.log('update-status reply:', JSON.stringify(s).slice(0, 300));
  ws.close();
  process.exit(0);
});

setTimeout(() => { console.error('timeout'); process.exit(1); }, 15000);
