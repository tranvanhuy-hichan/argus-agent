// Ứng dụng desktop Argus Agent: mở một cửa sổ riêng, bên trong là giao diện web do server Argus (đóng gói sẵn) phục vụ.
// Người dùng không cần biết server, cổng hay dòng lệnh: bấm mở là dùng được. Dữ liệu nằm ở thư mục dữ liệu của người dùng.
const { app, BrowserWindow, Menu, dialog, nativeTheme, shell } = require('electron')
const { spawn, execFileSync } = require('node:child_process')
const fs = require('node:fs')
const path = require('node:path')

const PREFERRED_PORT = 18787 // cố định để đăng nhập OAuth của MCP còn hiệu lực ở lần mở sau
const START_TIMEOUT_MS = 90_000
const vi = app.getLocale().toLowerCase().startsWith('vi')
const L = (a, b) => (vi ? a : b)

let win = null
let server = null
let origin = null
let quitting = false
let logStream = null

function log(msg) {
  try {
    if (!logStream) logStream = fs.createWriteStream(path.join(app.getPath('userData'), 'server.log'), { flags: 'a' })
    logStream.write(`[${new Date().toISOString()}] ${msg}\n`)
  } catch { /* không ghi được nhật ký thì bỏ qua */ }
}
process.on('uncaughtException', (e) => { log(`uncaughtException: ${e.stack || e}`); })
process.on('unhandledRejection', (e) => { log(`unhandledRejection: ${e && e.stack ? e.stack : e}`) })

function serverCommand() {
  const exe = process.platform === 'win32' ? 'argus-server.exe' : 'argus-server'
  const packed = path.join(process.resourcesPath, 'server', exe)
  if (fs.existsSync(packed)) return { cmd: packed, args: [], cwd: path.dirname(packed) }
  if (process.env.ARGUS_SERVER) return { cmd: process.env.ARGUS_SERVER, args: [], cwd: undefined }
  // chạy từ mã nguồn (npm start): dùng Python của repo
  const backend = path.resolve(__dirname, '..', 'backend')
  const py = process.env.ARGUS_PYTHON || path.resolve(__dirname, '..', '..', '.venv', 'bin', 'python')
  return { cmd: fs.existsSync(py) ? py : 'python3', args: ['-m', 'argus.desktop_server'], cwd: backend }
}

function startServer() {
  const dataDir = process.env.ARGUS_HOME || path.join(app.getPath('userData'), 'data')
  fs.mkdirSync(dataDir, { recursive: true })
  const { cmd, args, cwd } = serverCommand()
  log(`starting server: ${cmd} ${args.join(' ')} (data: ${dataDir})`)
  server = spawn(cmd, [...args, '--port', String(PREFERRED_PORT)], {
    cwd, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'],
    env: { ...process.env, ARGUS_HOME: dataDir, PYTHONUTF8: '1', PYTHONUNBUFFERED: '1' },
  })
  server.stderr.on('data', (d) => logStream.write(d))
  return new Promise((resolve, reject) => {
    let buf = ''
    const timer = setTimeout(() => reject(new Error(L('Server khởi động quá lâu.', 'The server took too long to start.'))), START_TIMEOUT_MS)
    server.stdout.on('data', (d) => {
      logStream.write(d)
      buf += d.toString()
      const m = buf.match(/ARGUS_READY (\d+)/)
      if (m) { clearTimeout(timer); resolve(Number(m[1])) }
    })
    server.on('error', (e) => { clearTimeout(timer); reject(e) })
    server.on('exit', (code) => {
      clearTimeout(timer)
      if (!origin) reject(new Error(L(`Server dừng với mã ${code}.`, `The server exited with code ${code}.`)))
      else if (!quitting) onServerCrashed(code)
    })
  })
}

function stopServer() {
  if (!server || server.exitCode !== null) return
  try {
    if (process.platform === 'win32') execFileSync('taskkill', ['/pid', String(server.pid), '/T', '/F'], { stdio: 'ignore' })
    else { server.kill('SIGTERM'); setTimeout(() => { try { server.kill('SIGKILL') } catch { /* đã thoát */ } }, 3000).unref() }
  } catch { /* tiến trình đã thoát */ }
}

async function onServerCrashed(code) {
  const r = await dialog.showMessageBox(win ?? undefined, {
    type: 'error', buttons: [L('Khởi động lại', 'Restart'), L('Thoát', 'Quit')], defaultId: 0, cancelId: 1,
    message: L('Argus đã dừng đột ngột', 'Argus stopped unexpectedly'),
    detail: L(`Mã thoát: ${code}. Nhật ký: ${path.join(app.getPath('userData'), 'server.log')}`, `Exit code: ${code}. Log: ${path.join(app.getPath('userData'), 'server.log')}`),
  })
  if (r.response === 0) { app.relaunch(); }
  quitting = true
  app.quit()
}

const img = (name) => { try { return 'data:image/png;base64,' + fs.readFileSync(path.join(__dirname, 'assets', name)).toString('base64') } catch { return '' } }

// Màn hình chào hiện ngay khi mở app, trong lúc máy chủ nội bộ khởi động: logo lớn, tên và khẩu hiệu, theo giao diện sáng/tối của hệ điều hành.
const splash = (msg) => {
  const dark = nativeTheme.shouldUseDarkColors
  const bg = dark ? '#0c0c0e' : '#ffffff'
  const fg = dark ? '#eef0f6' : '#14213d'
  const muted = dark ? '#9a9aa5' : '#5b6475'
  const mark = img(dark ? 'argus-mark.png' : 'argus-mark-light.png')
  const word = img('argus-wordmark.png')
  const slogan = 'Intelligence that works the way you do.'  // luôn bằng tiếng Anh
  return 'data:text/html;charset=utf-8,' + encodeURIComponent(`<!doctype html><meta charset="utf-8"><title>Argus</title><style>
body{margin:0;height:100vh;display:grid;place-items:center;background:${bg};color:${muted};font:16px system-ui,sans-serif;overflow:hidden}
.c{display:flex;flex-direction:column;align-items:center;text-align:center;padding:0 24px}
.mark{height:min(30vh,150px)}
.word{display:block;height:min(8vh,38px);aspect-ratio:7.33/1;margin-top:22px;background:${fg};-webkit-mask:url(${word}) center/contain no-repeat;mask:url(${word}) center/contain no-repeat}
.s{margin:30px 0 0;max-width:460px;font-size:17px;line-height:1.5}
.bar{margin-top:38px;width:160px;height:2px;border-radius:2px;background:${dark ? '#1c1c22' : '#e5e8ee'};overflow:hidden}
.bar i{display:block;width:33%;height:100%;background:#2563eb;border-radius:2px;animation:s 1.2s ease-in-out infinite}
.m{margin-top:14px;font-size:12px;opacity:.8}
@keyframes s{from{transform:translateX(-100%)}to{transform:translateX(300%)}}
</style><div class="c"><img class="mark" src="${mark}" alt=""><span class="word"></span><p class="s">${slogan}</p><div class="bar"><i></i></div><div class="m">${msg}</div></div>`)
}

function createWindow() {
  win = new BrowserWindow({
    width: 1360, height: 880, minWidth: 900, minHeight: 600, show: false, backgroundColor: nativeTheme.shouldUseDarkColors ? '#0c0c0e' : '#ffffff', title: 'Argus Agent',
    icon: path.join(__dirname, 'assets', 'icon.png'), autoHideMenuBar: true,
    webPreferences: { contextIsolation: true, sandbox: true, nodeIntegration: false },
  })
  win.once('ready-to-show', () => win.show())
  win.on('closed', () => { win = null })
  // liên kết ra ngoài mở bằng trình duyệt hệ thống, không mở trong cửa sổ app
  win.webContents.setWindowOpenHandler(({ url }) => { if (/^https?:/i.test(url)) shell.openExternal(url); return { action: 'deny' } })
  win.webContents.on('will-navigate', (e, url) => { if (origin && !url.startsWith(origin)) { e.preventDefault(); if (/^https?:/i.test(url)) shell.openExternal(url) } })
  void win.loadURL(splash(L('Đang khởi động Argus…', 'Starting Argus…')))
}

function buildMenu() {
  Menu.setApplicationMenu(Menu.buildFromTemplate([
    ...(process.platform === 'darwin' ? [{ role: 'appMenu' }] : []),
    { role: 'editMenu' },
    { label: L('Xem', 'View'), submenu: [{ role: 'reload' }, { role: 'togglefullscreen' }, { type: 'separator' }, { role: 'resetZoom' }, { role: 'zoomIn' }, { role: 'zoomOut' }] },
    { label: L('Trợ giúp', 'Help'), submenu: [
      { label: L('Mở thư mục dữ liệu', 'Open data folder'), click: () => shell.openPath(app.getPath('userData')) },
      { label: L('Xem nhật ký', 'View log'), click: () => shell.openPath(path.join(app.getPath('userData'), 'server.log')) },
      { type: 'separator' },
      { role: 'quit' },
    ] },
  ]))
}

if (!app.requestSingleInstanceLock()) {
  app.quit()
} else {
  app.on('second-instance', () => { if (win) { if (win.isMinimized()) win.restore(); win.focus() } })
  app.whenReady().then(async () => {
    log('app ready')
    buildMenu()
    createWindow()
    log('window created')
    try {
      const port = await startServer()
      origin = `http://127.0.0.1:${port}`
      log(`server ready on ${origin}`)
      if (win) await win.loadURL(origin)
    } catch (e) {
      log(`start failed: ${e.stack || e}`)
      stopServer()
      await dialog.showMessageBox({ type: 'error', message: L('Không khởi động được Argus', 'Argus could not start'),
        detail: `${e.message}\n\n${L('Nhật ký', 'Log')}: ${path.join(app.getPath('userData'), 'server.log')}` })
      quitting = true
      app.quit()
    }
  })
  app.on('window-all-closed', () => app.quit())
  app.on('before-quit', () => { quitting = true; stopServer() })
}
