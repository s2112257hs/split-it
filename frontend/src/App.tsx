import { useEffect, useState } from "react";
import HomePage from "./pages/HomePage";
import BillSplitDetailPage from "./pages/BillSplitDetailPage";
import RunningBalances from "./pages/RunningBalances";
import SettleBalances from "./pages/SettleBalances";
import SplitFlow from "./pages/SplitFlow";
import ViewBillsPage from "./pages/ViewBillsPage";

type AppRoute = "home" | "split" | "balances" | "settle" | "viewBills" | "billDetails";

function billIdFromPath(pathname: string): string | null {
  if (!pathname.startsWith("/bills/")) {
    return null;
  }

  const rawId = pathname.slice("/bills/".length);
  const decodedId = decodeURIComponent(rawId.trim());
  return decodedId || null;
}

function routeFromPath(pathname: string): AppRoute {
  if (pathname === "/split") {
    return "split";
  }

  if (pathname === "/balances") {
    return "balances";
  }

  if (pathname === "/settle") {
    return "settle";
  }

  if (pathname === "/bills") {
    return "viewBills";
  }

  if (billIdFromPath(pathname)) {
    return "billDetails";
  }

  return "home";
}

function navigate(pathname: string, setRoute: (route: AppRoute) => void) {
  window.history.pushState({}, "", pathname);
  setRoute(routeFromPath(pathname));
}

export default function App() {
  const [route, setRoute] = useState<AppRoute>(() => routeFromPath(window.location.pathname));
  const [activeBillId, setActiveBillId] = useState<string | null>(() => billIdFromPath(window.location.pathname));
  const apiBase = import.meta.env.VITE_API_BASE_URL ?? "";

  useEffect(() => {
    const handlePopState = () => {
      const pathname = window.location.pathname;
      setRoute(routeFromPath(pathname));
      setActiveBillId(billIdFromPath(pathname));
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

  if (route === "settle") {
    return <SettleBalances apiBase={apiBase} onBackHome={() => navigate("/", setRoute)} />;
  }

  if (route === "viewBills") {
    return (
      <ViewBillsPage
        apiBase={apiBase}
        onBackHome={() => navigate("/", setRoute)}
        onOpenBill={(receiptImageId) => {
          setActiveBillId(receiptImageId);
          navigate(`/bills/${encodeURIComponent(receiptImageId)}`, setRoute);
        }}
      />
    );
  }

  if (route === "billDetails" && activeBillId) {
    return (
      <BillSplitDetailPage
        apiBase={apiBase}
        receiptImageId={activeBillId}
        onBackHome={() => navigate("/", setRoute)}
        onBackToBills={() => navigate("/bills", setRoute)}
      />
    );
  }

  return (
    <HomePage
      onAddBill={() => navigate("/split", setRoute)}
      onViewBills={() => navigate("/bills", setRoute)}
      onCheckBalances={() => navigate("/balances", setRoute)}
      onSettleBalances={() => navigate("/settle", setRoute)}
    />
  );
}
