import { useEffect, useState } from "react";
import HomePage from "./pages/HomePage";
import RunningBalances from "./pages/RunningBalances";
import SplitFlow from "./pages/SplitFlow";

type AppRoute = "home" | "split" | "balances";

function routeFromPath(pathname: string): AppRoute {
  if (pathname === "/split") {
    return "split";
  }

  if (pathname === "/balances") {
    return "balances";
  }

  return "home";
}

function navigate(pathname: string, setRoute: (route: AppRoute) => void) {
  window.history.pushState({}, "", pathname);
  setRoute(routeFromPath(pathname));
}

export default function App() {
  const [route, setRoute] = useState<AppRoute>(() => routeFromPath(window.location.pathname));
  const apiBase = import.meta.env.VITE_API_BASE_URL ?? "";

  useEffect(() => {
    const handlePopState = () => {
      setRoute(routeFromPath(window.location.pathname));
    };

    window.addEventListener("popstate", handlePopState);

    return () => {
      window.removeEventListener("popstate", handlePopState);
    };
  }, []);

  if (route === "split") {
    return <SplitFlow onBackHome={() => navigate("/", setRoute)} />;
  }

  if (route === "balances") {
    return <RunningBalances apiBase={apiBase} onBackHome={() => navigate("/", setRoute)} />;
  }

  return <HomePage onAddBill={() => navigate("/split", setRoute)} onCheckBalances={() => navigate("/balances", setRoute)} />;
}
