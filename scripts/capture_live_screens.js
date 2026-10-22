const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

const ROOT_DIR = path.resolve(__dirname, '..');
const PY_EXE = path.resolve(ROOT_DIR, '.venv/Scripts/python.exe');
const CHROME_EXE = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';

const DEMO_USERS = {
  HOLDER: {
    id: "usr_local_holder",
    username: "holder@example.test",
    displayName: "Local Holder",
    name: "Demo Holder (Charaf Eddine Bessanane)",
    email: "holder@example.test",
    nationalId: "DEMO-HOLD-829104",
    organization: "Demo Academic Wallet [DEMO ENVIRONMENT]",
    did: "did:key:z6MkuBesnaSecureHolder2026Ed25519",
    walletAddress: "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
    role: "HOLDER",
    assuranceLevel: "HIGH"
  },
  ISSUER: {
    id: "usr_local_issuer",
    username: "issuer@example.test",
    displayName: "Local Issuer",
    name: "Demo University Authority",
    email: "issuer@example.test",
    nationalId: "DEMO-ISS-102938",
    organization: "Demo University (Accredited Issuer) [DEMO ENVIRONMENT]",
    did: "did:ssi:platform:governance-authority",
    walletAddress: "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
    role: "ISSUER",
    assuranceLevel: "HIGH"
  },
  VERIFIER: {
    id: "usr_local_verifier",
    username: "verifier@example.test",
    displayName: "Local Verifier",
    name: "Demo Company Compliance",
    email: "verifier@example.test",
    nationalId: "DEMO-VRF-475829",
    organization: "Demo Company (Trust Verification) [DEMO ENVIRONMENT]",
    did: "did:verifier:platform:compliance-office",
    walletAddress: "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
    role: "VERIFIER",
    assuranceLevel: "HIGH"
  },
  GUARDIAN: {
    id: "usr_local_admin",
    username: "admin@example.test",
    displayName: "Local Guardian & Admin",
    name: "Demo Quorum Guardian #1",
    email: "admin@example.test",
    nationalId: "DEMO-GRD-938201",
    organization: "Demo Social Recovery Network [DEMO ENVIRONMENT]",
    did: "did:guardian:social-recovery:quorum-member",
    walletAddress: "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
    role: "ADMIN",
    assuranceLevel: "HIGH"
  },
  ADMIN: {
    id: "usr_local_admin",
    username: "admin@example.test",
    displayName: "Local Admin",
    name: "Demo System Administrator",
    email: "admin@example.test",
    nationalId: "DEMO-ADM-000001",
    organization: "Demo Platform Operations [DEMO ENVIRONMENT]",
    did: "did:admin:platform:system-operator",
    walletAddress: "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266",
    role: "ADMIN",
    assuranceLevel: "HIGH"
  }
};

const CREDENTIALS = {
  HOLDER: { username: "holder@example.test", password: "Holder-Prototype-2026!" },
  ISSUER: { username: "issuer@example.test", password: "Issuer-Prototype-2026!" },
  VERIFIER: { username: "verifier@example.test", password: "Verifier-Prototype-2026!" },
  GUARDIAN: { username: "admin@example.test", password: "Admin-Prototype-2026!" },
  ADMIN: { username: "admin@example.test", password: "Admin-Prototype-2026!" }
};

const TARGETS = [
  // 1. Public & Educational Views
  { id: 'SCR-PUB-01', route: '/', persona: null, wait: 2000, desc: 'Platform Landing & Golden Path Overview' },
  { id: 'SCR-PUB-02', route: '/ecosystem', persona: null, wait: 2000, desc: 'Accredited Ecosystem Trust Registry' },
  { id: 'SCR-PUB-03', route: '/docs', persona: null, wait: 2000, desc: 'Technical Architecture & Standards Specification' },
  { id: 'SCR-PUB-04', route: '/login', persona: null, wait: 2000, desc: 'Unified Authentication & 1-Click Persona Chooser' },

  // 2. Holder Wallet Experience (including canonical alias URLs)
  { id: 'SCR-HLD-01', route: '/wallet', persona: 'HOLDER', wait: 2500, desc: 'Sovereign Credential Dashboard & Tactile Cards' },
  { id: 'SCR-HLD-02', route: '/wallet/credentials/vc-academic-diploma-001', persona: 'HOLDER', wait: 2000, desc: 'Verifiable Credential Deep Inspection View' },
  { id: 'SCR-HLD-02B', route: '/credentials/vc-academic-diploma-001', persona: 'HOLDER', wait: 2000, desc: 'Canonical Direct Credential Detail Route' },
  { id: 'SCR-HLD-03', route: '/wallet/scan', persona: 'HOLDER', wait: 2000, desc: 'OID4VCI Credential Offer QR Ingestion' },
  { id: 'SCR-HLD-04', route: '/wallet/consent', persona: 'HOLDER', wait: 2000, desc: 'Selective Disclosure & Privacy Consent Cockpit' },
  { id: 'SCR-HLD-04B', route: '/consent/presentation', persona: 'HOLDER', wait: 2000, desc: 'Canonical Direct Presentation Consent Route' },
  { id: 'SCR-HLD-05', route: '/wallet/activity', persona: 'HOLDER', wait: 2000, desc: 'Holder Verification & Consent History Log' },
  { id: 'SCR-HLD-06', route: '/wallet/security', persona: 'HOLDER', wait: 2000, desc: 'Key Custody & Guardian Assignment Console' },

  // 3. Issuer Organization Portal
  { id: 'SCR-ISS-01', route: '/issuer', persona: 'ISSUER', wait: 2500, desc: 'Accredited Authority Dashboard & Metrics' },
  { id: 'SCR-ISS-02', route: '/issuer/templates', persona: 'ISSUER', wait: 2000, desc: 'Verifiable Credential Schema & Template Builder' },
  { id: 'SCR-ISS-03', route: '/issuer/issue', persona: 'ISSUER', wait: 2000, desc: '3-Step Credential Issuance Wizard' },
  { id: 'SCR-ISS-04', route: '/issuer/revocations', persona: 'ISSUER', wait: 2000, desc: 'W3C Bitstring Status List 1.0 Revocation Console' },

  // 4. Verifier Portal & Verification Engine
  { id: 'SCR-VRF-01', route: '/verifier', persona: 'VERIFIER', wait: 2500, desc: 'Relying Party Dashboard & Request Overview' },
  { id: 'SCR-VRF-02', route: '/verifier/request', persona: 'VERIFIER', wait: 2000, desc: 'OID4VP Presentation Request Builder' },
  { id: 'SCR-VRF-03', route: '/verifier/request', persona: 'VERIFIER', action: 'generate-oid4vp', wait: 2500, desc: 'Presentation Request QR Code & Deep Link' },
  { id: 'SCR-VRF-04', route: '/verifier/verify', persona: 'VERIFIER', action: 'run-verification', wait: 3500, desc: 'Live 9-Point Trust Verification Result Card' },
  { id: 'SCR-VRF-05', route: '/verifier/history', persona: 'VERIFIER', wait: 2000, desc: 'Verifier Presentation Audit & Replay Archive' },

  // 5. Guardian Social Recovery Network
  { id: 'SCR-GRD-01', route: '/guardian', persona: 'GUARDIAN', wait: 2500, desc: 'Guardian Network Dashboard & Assigned Wallets' },
  { id: 'SCR-GRD-02', route: '/guardian/requests', persona: 'GUARDIAN', wait: 2000, desc: 'Active Recovery Petitions Queue' },
  { id: 'SCR-GRD-03', route: '/guardian/approve/req-001', persona: 'GUARDIAN', wait: 2000, desc: 'Quorum Share Submission & Time-Lock Visualizer' },

  // 6. Administrator Operations Cockpit
  { id: 'SCR-ADM-01', route: '/admin', persona: 'ADMIN', wait: 2500, desc: 'System Telemetry & Microservices Health Matrix' },
  { id: 'SCR-ADM-02', route: '/admin/contracts', persona: 'ADMIN', wait: 2000, desc: 'EVM Smart Contracts & On-Chain State Explorer' },
  { id: 'SCR-ADM-03', route: '/admin/audit', persona: 'ADMIN', wait: 2000, desc: 'Tamper-Evident Outbox & Security Audit Trail' },
  { id: 'SCR-ADM-04', route: '/admin/fraud-monitor', persona: 'ADMIN', wait: 2000, desc: 'Real-Time AI Fraud Threat Stream & Confusion Matrix' }
];

async function pollHealth(url, timeoutMs = 15000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      const res = await fetch(url);
      if (res.ok) return true;
    } catch {}
    await new Promise((r) => setTimeout(r, 400));
  }
  return false;
}

async function main() {
  console.log('=== SECURE SSI PLATFORM: LIVE EVIDENCE AUTOMATION ===\n');

  const children = [];

  function spawnProcess(cmd, args, cwd) {
    const proc = spawn(cmd, args, { cwd, stdio: ['ignore', 'pipe', 'pipe'] });
    children.push(proc);
    return proc;
  }

  try {
    // 1. Check/Spawn Identity Service
    let idUp = await pollHealth('http://127.0.0.1:8001/health', 1000);
    if (!idUp) {
      console.log('Spawning Identity Service (port 8001)...');
      spawnProcess(PY_EXE, ['-m', 'uvicorn', 'app.main:app', '--port', '8001', '--host', '127.0.0.1'], path.resolve(ROOT_DIR, 'services/identity-service'));
      idUp = await pollHealth('http://127.0.0.1:8001/health', 10000);
    }
    console.log(idUp ? '✔ Identity Service ready on :8001' : '✖ Identity Service failed to start');

    // 2. Check/Spawn API Gateway
    let gwUp = await pollHealth('http://127.0.0.1:8000/health', 1000);
    if (!gwUp) {
      console.log('Spawning API Gateway (port 8000)...');
      spawnProcess(PY_EXE, ['-m', 'uvicorn', 'app.main:app', '--port', '8000', '--host', '127.0.0.1'], path.resolve(ROOT_DIR, 'services/api-gateway'));
      gwUp = await pollHealth('http://127.0.0.1:8000/health', 10000);
    }
    console.log(gwUp ? '✔ API Gateway ready on :8000' : '✖ API Gateway failed to start');

    // 3. Check/Spawn Fraud Service
    let fraudUp = await pollHealth('http://127.0.0.1:8002/health', 1000);
    if (!fraudUp) {
      console.log('Spawning Fraud Service (port 8002)...');
      spawnProcess(PY_EXE, ['-m', 'uvicorn', 'app.main:app', '--port', '8002', '--host', '127.0.0.1'], path.resolve(ROOT_DIR, 'services/fraud-service'));
      fraudUp = await pollHealth('http://127.0.0.1:8002/health', 10000);
    }
    console.log(fraudUp ? '✔ Fraud Service ready on :8002' : '✖ Fraud Service failed to start');

    // 4. Check/Spawn Recovery Service
    let recUp = await pollHealth('http://127.0.0.1:8003/health', 1000);
    if (!recUp) {
      console.log('Spawning Recovery Service (port 8003)...');
      spawnProcess(PY_EXE, ['-m', 'uvicorn', 'app.main:app', '--port', '8003', '--host', '127.0.0.1'], path.resolve(ROOT_DIR, 'services/recovery-service'));
      recUp = await pollHealth('http://127.0.0.1:8003/health', 10000);
    }
    console.log(recUp ? '✔ Recovery Service ready on :8003' : '✖ Recovery Service failed to start');

    // 5. Check/Spawn Vite
    let viteUp = await pollHealth('http://127.0.0.1:5173/', 1000);
    if (!viteUp) {
      console.log('Spawning Vite Frontend (port 5173)...');
      spawnProcess('cmd.exe', ['/c', 'npx.cmd', 'vite', '--host', '127.0.0.1', '--port', '5173'], path.resolve(ROOT_DIR, 'apps/web'));
      viteUp = await pollHealth('http://127.0.0.1:5173/', 15000);
    }
    console.log(viteUp ? '✔ Vite Frontend ready on :5173' : '✖ Vite Frontend failed to start');

    // 6. Fetch live tokens
    console.log('\nAcquiring live JWTs for all roles...');
    const tokens = {};
    for (const [role, cred] of Object.entries(CREDENTIALS)) {
      try {
        const res = await fetch('http://127.0.0.1:8001/api/v1/auth/token', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(cred)
        });
        if (res.ok) {
          const data = await res.json();
          tokens[role] = data.accessToken;
          console.log(`  ✔ JWT for ${role} acquired`);
        } else {
          console.warn(`  ⚠ Token failed for ${role}: HTTP ${res.status}`);
        }
      } catch (err) {
        console.warn(`  ⚠ Error acquiring token for ${role}:`, err.message);
      }
    }

    // 7. Launch Headless Chrome
    console.log('\nLaunching Chrome 128+ Headless on CDP port 9666...');
    const userDataDir = 'C:\\temp\\chrome-ssi-runner';
    const chromeProc = spawn(CHROME_EXE, [
      '--headless=new',
      '--no-sandbox',
      '--disable-gpu',
      '--remote-debugging-port=9666',
      `--user-data-dir=${userDataDir}`,
      '--no-first-run',
      '--no-default-browser-check'
    ]);
    children.push(chromeProc);

    let versionData = null;
    for (let i = 0; i < 40; i++) {
      try {
        const res = await fetch('http://127.0.0.1:9666/json/version');
        if (res.ok) {
          versionData = await res.json();
          break;
        }
      } catch {}
      await new Promise((r) => setTimeout(r, 250));
    }

    if (!versionData) throw new Error('Could not connect to Chrome CDP on 9666');
    console.log('✔ Connected to Browser:', versionData.Browser);

    // 8. Open Target & WebSocket
    const newRes = await fetch('http://127.0.0.1:9666/json/new?about:blank', { method: 'PUT' });
    const pageTarget = await newRes.json();
    const ws = new WebSocket(pageTarget.webSocketDebuggerUrl);

    let idCounter = 1;
    const pending = new Map();

    function send(method, params = {}) {
      return new Promise((resolve, reject) => {
        const id = idCounter++;
        pending.set(id, { resolve, reject });
        ws.send(JSON.stringify({ id, method, params }));
      });
    }

    ws.onmessage = (e) => {
      const d = JSON.parse(e.data);
      if (d.id && pending.has(d.id)) {
        const { resolve, reject } = pending.get(d.id);
        pending.delete(d.id);
        if (d.error) reject(new Error(d.error.message));
        else resolve(d.result);
      }
    };

    await new Promise((r) => { ws.onopen = r; });

    await send('Page.enable');
    await send('Runtime.enable');
    await send('Emulation.setDeviceMetricsOverride', {
      width: 1920,
      height: 1080,
      deviceScaleFactor: 1,
      mobile: false
    });

    const outDir = path.resolve(ROOT_DIR, 'docs/screenshots');
    if (!fs.existsSync(outDir)) {
      fs.mkdirSync(outDir, { recursive: true });
    }

    console.log(`\nBeginning sequential capture of ${TARGETS.length} screens:\n`);
    const results = [];

    for (let idx = 0; idx < TARGETS.length; idx++) {
      const t = TARGETS[idx];
      const fullUrl = `http://127.0.0.1:5173${t.route}`;
      const filename = `${t.id}.png`;
      const dest = path.join(outDir, filename);

      process.stdout.write(`[${idx + 1}/${TARGETS.length}] ${t.id} -> ${t.route} (${t.persona || 'PUBLIC'})... `);

      try {
        if (t.persona && DEMO_USERS[t.persona]) {
          const userObj = DEMO_USERS[t.persona];
          const token = tokens[t.persona] || '';
          await send('Runtime.evaluate', {
            expression: `
              localStorage.setItem("secure_ssi_user", JSON.stringify(${JSON.stringify(userObj)}));
              localStorage.setItem("ssi_access_token", ${JSON.stringify(token)});
              localStorage.setItem("secure_ssi_token", ${JSON.stringify(token)});
            `
          });
        } else {
          await send('Runtime.evaluate', {
            expression: `
              localStorage.removeItem("secure_ssi_user");
              localStorage.removeItem("ssi_access_token");
              localStorage.removeItem("secure_ssi_token");
            `
          });
        }

        await send('Page.navigate', { url: fullUrl });
        await new Promise((r) => setTimeout(r, t.wait));

        if (t.action === 'generate-oid4vp') {
          await send('Runtime.evaluate', {
            expression: `
              (() => {
                const btn = Array.from(document.querySelectorAll('button')).find(b => 
                  b.innerText.includes('Generate') || b.innerText.includes('OID4VP') || b.type === 'submit'
                );
                if (btn) btn.click();
              })()
            `
          });
          await new Promise((r) => setTimeout(r, 2000));
        } else if (t.action === 'run-verification') {
          await send('Runtime.evaluate', {
            expression: `
              (() => {
                const btn = Array.from(document.querySelectorAll('button')).find(b => 
                  b.innerText.includes('Run') || b.innerText.includes('Verification')
                );
                if (btn) btn.click();
              })()
            `
          });
          await new Promise((r) => setTimeout(r, 3000));
        }

        // Capture screenshot
        const shot = await send('Page.captureScreenshot', { format: 'png' });
        const buf = Buffer.from(shot.data, 'base64');
        fs.writeFileSync(dest, buf);

        // Visual assessment heuristic:
        // A broken / refused connection produces a blank error page of < 30KB.
        // A rendered app shell with dark theme and typography is > 60KB.
        const isRendered = buf.length > 50000;
        const visualQuality = isRendered ? 'PASS' : 'NEEDS_REWORK';

        console.log(`✔ OK (${buf.length.toLocaleString()} bytes) -> [${visualQuality}]`);
        results.push({
          id: t.id,
          route: t.route,
          persona: t.persona || 'PUBLIC',
          desc: t.desc,
          filename,
          sizeBytes: buf.length,
          visualQuality,
          status: 'CAPTURED'
        });
      } catch (err) {
        console.log(`✖ ERROR: ${err.message}`);
        results.push({
          id: t.id,
          route: t.route,
          persona: t.persona || 'PUBLIC',
          desc: t.desc,
          filename,
          sizeBytes: 0,
          visualQuality: 'BLOCKED',
          status: 'FAILED',
          error: err.message
        });
      }
    }

    ws.close();

    console.log('\n=== CAPTURE SUMMARY ===');
    console.log(`Total Target Screens: ${TARGETS.length}`);
    const passed = results.filter(r => r.visualQuality === 'PASS');
    console.log(`Visual PASS: ${passed.length} / ${TARGETS.length}`);

    const metaPath = path.resolve(ROOT_DIR, 'reports/screenshots_manifest.json');
    fs.writeFileSync(metaPath, JSON.stringify(results, null, 2));
    console.log(`Manifest saved to: ${metaPath}`);

  } finally {
    console.log('\nTearing down child processes...');
    for (const proc of children) {
      try {
        proc.kill('SIGTERM');
      } catch {}
    }
  }
}

main().catch(err => {
  console.error('Fatal execution error:', err);
  process.exit(1);
});
