// 에이전트 카드 등록 로직 전용 라우터
// - 데이터 저장: solution/data/agents.json
// - 등록(관리자 전용): POST /api/agents

const path = require('path');
const fs = require('fs');
const express = require('express');
const http = require('http');
const https = require('https');

const router = express.Router();

//-------------------------------
// 토큰 검증 유틸 (회사 정책 알잘딱)
//-------------------------------

// 관리자 이메일(기본 admin@example.com)
const ADMIN_EMAIL = process.env.ADMIN_EMAIL || 'admin@example.com';
// 검증 서버: 8000 포트의 /users/me 고정 호출
const USERME_DIRECT_URL = process.env.USERME_DIRECT_URL || 'http://127.0.0.1:8000/users/me';

// 에러 응답 헬퍼 (일관된 포맷 유지)
function sendError(res, status, code, message) {
  return res.status(status).json({ error: code, message });
}

// 간단한 HTTP GET(JSON) 유틸
function getJson(url, headers = {}) {
  return new Promise((resolve, reject) => {
    const isHttps = url.startsWith('https://');
    const lib = isHttps ? https : http;
    const req = lib.request(url, { method: 'GET', headers }, (resp) => {
      let body = '';
      resp.setEncoding('utf8');
      resp.on('data', (chunk) => (body += chunk));
      resp.on('end', () => {
        try {
          const json = JSON.parse(body || '{}');
          resolve({ status: resp.statusCode || 0, json });
        } catch (e) {
          reject(new Error('BAD_JSON'));
        }
      });
    });
    req.on('error', reject);
    req.end();
  });
}

// /users/me 호출로 토큰 유효성 확인
async function getUserMe(userToken) {
  return getJson(USERME_DIRECT_URL, {
    Authorization: `Bearer ${userToken}`,
    Accept: 'application/json',
  });
}

// - 200 + {email} → 유효 (req.jwt.sub = email)
// - 401 + {detail:"Invalid token"} → 401 INVALID_TOKEN
function requireJwt(req, res, next) {
  const auth = req.headers['authorization'];
  if (!auth) return sendError(res, 401, 'TOKEN_MISSING', 'Missing Authorization header');
  const [scheme, token] = String(auth).split(' ');
  if (scheme !== 'Bearer' || !token) {
    return sendError(res, 401, 'INVALID_AUTH_FORMAT', 'Expected: Authorization: Bearer <token>');
  }
  getUserMe(token)
    .then(({ status, json }) => {
      if (status === 200 && json && typeof json.email === 'string') {
        req.jwt = { sub: json.email };
        return next();
      }
      if (status === 401 && json && json.detail === 'Invalid token') {
        return sendError(res, 401, 'INVALID_TOKEN', 'Invalid or malformed token');
      }
      return sendError(res, 502, 'TOKEN_SERVICE_ERROR', 'Token service unavailable');
    })
    .catch(() => sendError(res, 502, 'TOKEN_SERVICE_ERROR', 'Token service unavailable'));
}

// 관리자 권한 확인 (ADMIN_EMAIL과 일치해야 함)
function requireAdmin(req, res, next) {
  const email = req.jwt && req.jwt.sub;
  if (!email) return sendError(res, 401, 'INVALID_TOKEN', 'Invalid or malformed token');
  if (email !== ADMIN_EMAIL) return sendError(res, 403, 'FORBIDDEN', 'Admin privileges required');
  req.jwt = Object.assign({}, req.jwt, { role: 'admin' });
  return next();
}

// 토큰 검증 프록시 
router.get('/api/auth/me', (req, res) => {
  const auth = req.headers['authorization'];
  const [, token] = String(auth || '').split(' ');
  if (!token) return sendError(res, 401, 'TOKEN_MISSING', 'Missing Authorization header');
  getUserMe(token)
    .then(({ status, json }) => {
      if (status === 200 && json && typeof json.email === 'string') {
        return res.json({ email: json.email });
      }
      if (status === 401 && json && json.detail === 'Invalid token') {
        return sendError(res, 401, 'INVALID_TOKEN', 'Invalid or malformed token');
      }
      return sendError(res, 502, 'TOKEN_SERVICE_ERROR', 'Token service unavailable');
    })
    .catch(() => sendError(res, 502, 'TOKEN_SERVICE_ERROR', 'Token service unavailable'));
});



//-------------------------------
// 스키마 검증 로직
//-------------------------------


//-------------------------------
// 정책 검사 로직
//-------------------------------


//-------------------------------
// 데이터 저장 로직
//-------------------------------

const DATA_DIR = path.join(__dirname, 'data');
const DATA_FILE = path.join(DATA_DIR, 'agents.json');

function ensureDataFile() {
  if (!fs.existsSync(DATA_DIR)) fs.mkdirSync(DATA_DIR, { recursive: true });
  if (!fs.existsSync(DATA_FILE)) {
    const seed = [
      { name: 'Orchestrator', status: 'Active' },
      { name: 'Agent1', status: 'Active' },
      { name: 'Agent2', status: 'Active' },
      { name: 'Agent3', status: 'Active' },
      { name: 'Agent4', status: 'Active' },
      { name: 'Bridge', status: 'Active' },
    ];
    fs.writeFileSync(DATA_FILE, JSON.stringify(seed, null, 2));
  }
}

function loadAgents() {
  ensureDataFile();
  try {
    return JSON.parse(fs.readFileSync(DATA_FILE, 'utf8'));
  } catch (e) {
    return [];
  }
}

function saveAgents(list) {
  fs.writeFileSync(DATA_FILE, JSON.stringify(list, null, 2));
}

//-------------------------------
// 스키마 최소 검증
//-------------------------------

function validateAgentCard(card) {
  if (!card || typeof card !== 'object') return 'payload must be an object';
  if (!card.name || typeof card.name !== 'string') return 'name is required (string)';
  if (!card.url || typeof card.url !== 'string') return 'url is required (string)';
  if (!card.version || typeof card.version !== 'string') return 'version is required (string)';
  if (!card.protocolVersion || typeof card.protocolVersion !== 'string') return 'protocolVersion is required (string)';
  if (!card.capabilities || typeof card.capabilities !== 'object') return 'capabilities is required (object)';
  return null;
}

//-------------------------------
// 라우트 정의
//-------------------------------


// 에이전트 목록 조회 (공개)
router.get('/api/agents', (req, res) => {
  const raw = loadAgents();
  const agents = raw.map((item) => {
    if (item && item.card && item.card.name) {
      return { name: item.card.name, status: item.status || 'Active', card: item.card };
    }
    return item;
  });
  res.json({ agents });
});

// 에이전트 등록 (관리자 전용)
router.post('/api/agents', requireJwt, requireAdmin, (req, res) => {
  const body = req.body || {};
  const card = body.card && typeof body.card === 'object' ? body.card : body;
  const err = validateAgentCard(card);
  if (err) return res.status(400).json({ error: err });

  const agents = loadAgents();
  const exists = agents.find((a) => {
    const n = a?.card?.name || a?.name;
    return n && typeof n === 'string' && n.toLowerCase() === card.name.toLowerCase();
  });
  if (exists) return res.status(409).json({ error: 'Agent already exists' });

  const record = { card, status: 'Active' };
  agents.push(record);
  saveAgents(agents);
  return res.status(201).json({ agent: { name: card.name, status: 'Active', card } });
});

module.exports = router;
