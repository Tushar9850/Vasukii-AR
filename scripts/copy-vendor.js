// Copies model-viewer into www/ so the app works without a bundler.
const fs = require('fs');
const path = require('path');
const src = path.join(__dirname, '..', 'node_modules', '@google', 'model-viewer', 'dist', 'model-viewer.min.js');
const dstDir = path.join(__dirname, '..', 'www', 'vendor');
fs.mkdirSync(dstDir, { recursive: true });
fs.copyFileSync(src, path.join(dstDir, 'model-viewer.min.js'));
console.log('model-viewer copied to www/vendor');
