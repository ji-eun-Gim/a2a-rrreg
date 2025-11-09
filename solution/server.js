// 기본 모듈 및 라이브러리 불러오기
require('dotenv').config(); // .env 로드
const path = require('path');
const express = require('express');
const agentRouter = require('./agents-create');

const app = express();
const PORT = process.env.PORT || 3000;

// 정적 파일 서빙 (reg 디렉토리 전체)
app.use(express.static(__dirname));
// JSON 바디 파싱 (API 요청 처리용)
app.use(express.json());

// 루트 진입 시 agents.html 제공
app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'agents.html'));
});

// 보기 좋은 URL 매핑: /agents -> agents.html
app.get('/agents', (req, res) => {
  res.sendFile(path.join(__dirname, 'agents.html'));
});

// 에이전트 API 라우터 연결
app.use(agentRouter);

app.listen(PORT, () => {
  console.log(`Server running at http://localhost:${PORT}`);
});
