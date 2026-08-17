const { spawn } = require('child_process');
const path = require('path');

const pythonPath = 'C:\\Users\\Administrator\\AppData\\Local\\Microsoft\\WindowsApps\\PythonSoftwareFoundation.Python.3.13_qbz5n2kfra8p0\\python.exe';
const daemonScript = path.join(__dirname, 'daemon.py');

console.log(`[Launcher] Spawning Python daemon: ${pythonPath} ${daemonScript}`);

const child = spawn(pythonPath, [daemonScript], {
  cwd: __dirname,
  stdio: 'inherit'
});

child.on('error', (err) => {
  console.error('[Launcher] Failed to start child process:', err);
});

child.on('exit', (code, signal) => {
  console.log(`[Launcher] Python daemon exited with code ${code} and signal ${signal}`);
  process.exit(code || 0);
});
