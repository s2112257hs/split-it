type Props = {
  onAddBill: () => void;
  onCheckBalances: () => void;
};

export default function HomePage({ onAddBill, onCheckBalances }: Props) {
  return (
    <div className="app">
      <h1 className="h1">Split-It</h1>
      <div className="card formCard stack">
        <h2 className="stepTitle">Home</h2>
        <button className="btn btnPrimary" onClick={onAddBill}>Add a bill</button>
        <button className="btn" onClick={onCheckBalances}>Check running balances</button>
      </div>
    </div>
  );
}
