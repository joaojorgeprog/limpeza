const fs   = require('fs');
const path = require('path');

const ADMIN_EMAIL = 'admin@minde.pt';

function parseCookies(header) {
  if (!header) return {};
  return Object.fromEntries(
    header.split(';').map(c => {
      const [k, ...v] = c.trim().split('=');
      return [k.trim(), v.join('=')];
    })
  );
}

function verifyAdminToken(token) {
  if (!token) return false;
  try {
    // Descodificar payload JWT (base64url → JSON)
    const base64 = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
    const payload = JSON.parse(Buffer.from(base64, 'base64').toString('utf-8'));
    if (payload.email !== ADMIN_EMAIL) return false;
    if (payload.exp < Math.floor(Date.now() / 1000)) return false;
    return true;
  } catch {
    return false;
  }
}

module.exports = async function handler(req, res) {
  const cookies = parseCookies(req.headers.cookie);
  const token   = cookies['sb_admin'];

  if (!verifyAdminToken(token)) {
    // Não autenticado ou não é admin — redirecionar para o login
    res.setHeader('Location', '/?acesso=restrito');
    return res.status(302).end();
  }

  // Utilizador válido — servir o ficheiro
  const filePath = path.join(process.cwd(), 'plano.html');
  const html = fs.readFileSync(filePath, 'utf-8');

  res.setHeader('Content-Type', 'text/html; charset=utf-8');
  res.setHeader('Cache-Control', 'no-store, no-cache, must-revalidate');
  res.setHeader('X-Robots-Tag', 'noindex');
  return res.status(200).send(html);
};
