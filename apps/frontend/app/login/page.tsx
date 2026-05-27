import type { Metadata } from "next";

import { Nav } from "@/components/Nav";
import { SignInPanel } from "@/components/SignInPanel";
import { TerminalWindow } from "@/components/TerminalWindow";

export const metadata: Metadata = {
  title: "Sign in",
};

export default function LoginPage() {
  return (
    <div className="flex min-h-screen flex-col">
      <Nav />
      <main className="flex-1 px-6 py-12">
        <div className="mx-auto max-w-2xl">
          <TerminalWindow
            label="// AUTHENTICATION"
            heading={
              <>
                SIGN IN <span className="text-[#ccff00] glow-lime">WITH WALLET</span>
              </>
            }
          >
            <SignInPanel />
          </TerminalWindow>
        </div>
      </main>
    </div>
  );
}
