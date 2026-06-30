import pandas as pd


def calculate_fill_rate(orders: pd.DataFrame) -> float:
    return orders["units_shipped"].sum() / orders["units_ordered"].sum()


def flag_stockouts(inventory: pd.DataFrame) -> pd.DataFrame:
    return inventory.assign(stockout_risk=inventory["on_hand_units"] <= 0)
