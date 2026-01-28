# ai/features.py
import sqlite3
import pandas as pd


def build_features(db_path: str) -> str:
    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query("SELECT * FROM trades", conn)
    conn.close()
    if df.empty:
        return "No trades."
    df["risk"] = (df["entry"] - df["stop"]).abs()
    df["R"] = df["pnl"] / df["risk"].clip(lower=1e-9)
    summary = {
        "num_trades": int(len(df)),
        "win_rate": float((df["pnl"] > 0).mean()),
        "avg_R": float(df["R"].mean()),
        "best_symbol": df.groupby("symbol")["pnl"].sum().sort_values(ascending=False).head(1).to_dict(),
        "worst_symbol": df.groupby("symbol")["pnl"].sum().sort_values().head(1).to_dict(),
    }
    return str(summary)
