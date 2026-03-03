import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

// GENERATED SITE PASSWORD (keep this secret)
const PASSWORD = 'r7F$kLp9#V2mXzQ1';

export function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;

  // Allow static, next internals and the unlock page
  if (
    pathname.startsWith('/_next') ||
    pathname.startsWith('/api') ||
    pathname === '/unlock' ||
    pathname === '/favicon.ico'
  ) {
    return NextResponse.next();
  }

  const cookie = req.cookies.get('ks_auth')?.value;
  if (cookie === PASSWORD) return NextResponse.next();

  const url = req.nextUrl.clone();
  url.pathname = '/unlock';
  return NextResponse.redirect(url);
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico).*)']
};
