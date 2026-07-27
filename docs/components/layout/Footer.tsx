import Link from "next/link";

const GithubIcon = () => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    width="24"
    height="24"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    className="h-5 w-5"
  >
    <path d="M15 22v-4a4.8 4.8 0 0 0-1-3.02c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 2.48a13.38 13.38 0 0 0-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A4.8 4.8 0 0 0 8 18v4"></path>
  </svg>
);

export function Footer() {
  return (
    <footer className="border-t py-6 md:py-0">
      <div className="container flex flex-col items-center justify-between gap-4 md:h-24 md:flex-row mx-auto px-4">
        <div className="flex flex-col items-center gap-4 md:flex-row md:gap-2 px-8 md:px-0">
          <p className="text-center text-sm leading-loose text-muted-foreground md:text-left">
            Built for{" "}
            <a
              href="https://github.com/Aryan07175/GAM-360-Live-Reporting-Platform"
              target="_blank"
              rel="noreferrer"
              className="font-medium underline underline-offset-4"
            >
              GAM 360 Live Reporting Platform
            </a>
            . The source code is available on GitHub.
          </p>
        </div>
        <div className="flex items-center space-x-4">
          <Link
            href="https://github.com/Aryan07175/GAM-360-Live-Reporting-Platform"
            target="_blank"
            rel="noreferrer"
            className="text-muted-foreground hover:text-foreground"
          >
            <span className="sr-only">GitHub</span>
            <GithubIcon />
          </Link>
        </div>
      </div>
    </footer>
  );
}
