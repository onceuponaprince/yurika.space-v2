async function checkBackend(): Promise<{ status: string; checks: Record<string, string> } | null> {
  // Server components run inside the docker network, so use the internal URL.
  const url =
    process.env.INTERNAL_API_BASE_URL ??
    process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/api$/, '') ??
    'http://django:8000';
  try {
    const res = await fetch(`${url}/health/`, { cache: 'no-store' });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export default async function Home() {
  const health = await checkBackend();

  return (
    <main className="min-h-screen bg-black text-green-400 font-mono p-8">
      <div className="max-w-2xl mx-auto">
        <h1 className="text-4xl font-bold mb-2">yurika.space</h1>
        <p className="text-green-600 mb-8">// subsystem 1 — infra layer</p>

        <section className="border border-green-700 p-4 mb-4">
          <h2 className="text-xl mb-2">// backend health</h2>
          {health ? (
            <pre className="text-sm">{JSON.stringify(health, null, 2)}</pre>
          ) : (
            <p className="text-red-400">[unreachable] django backend is not responding</p>
          )}
        </section>

        <section className="border border-green-700 p-4">
          <h2 className="text-xl mb-2">// next subsystem</h2>
          <p>2 — auth (users app + SIWE + JWT)</p>
        </section>
      </div>
    </main>
  );
}
