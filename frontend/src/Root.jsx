import { useEffect, useState } from "react";
import App from "./App.jsx";
import Home from "./pages/Home.jsx";

// Minimal router: "/" landing, "/how", "/chart", "/model" info pages, "/app" = chat, form and results.
export default function Root() {
  const [path, setPath] = useState(window.location.pathname);
  const [start, setStart] = useState(null); // { mode, prompt } from the homepage

  useEffect(() => {
    const onPop = () => setPath(window.location.pathname);
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);

  function go(to) {
    if (to !== window.location.pathname) window.history.pushState({}, "", to);
    setPath(to);
    window.scrollTo(0, 0);
  }

  if (path.startsWith("/app")) {
    return <App start={start} onStartConsumed={() => setStart(null)} onHome={() => go("/")} />;
  }
  const page = { "/how": "how", "/chart": "chart", "/model": "model" }[path.replace(/\/$/, "")] || "home";
  return (
    <Home
      page={page}
      go={go}
      onStart={(s) => {
        setStart(s);
        go("/app");
      }}
    />
  );
}
