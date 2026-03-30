export function middleware(request) {
  const basicAuth = request.headers.get('authorization');

  if (basicAuth) {
    const auth = basicAuth.split(' ')[1];
    const [user, pwd] = atob(auth).split(':');
    if (pwd === 'restore123') {
      return; // allow
    }
  }

  return new Response('Access restricted — Winmar Emergency Dashboard', {
    status: 401,
    headers: {
      'WWW-Authenticate': 'Basic realm="Winmar Emergency Dashboard"',
    },
  });
}

export const config = {
  matcher: '/:path*',
};
