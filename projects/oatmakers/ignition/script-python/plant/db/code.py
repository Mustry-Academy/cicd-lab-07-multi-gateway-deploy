"""plant.db -- queries against the PlantDB connection (Part 2, database challenge)."""


def batches():
    """Rows from oat_batches, shaped for a Perspective table."""
    ds = system.db.runPrepQuery(
        "SELECT batch_code, recipe, kg_in, kg_out, started_at, finished_at "
        "FROM oat_batches ORDER BY started_at DESC",
        [],
        "PlantDB",
    )
    rows = []
    for row in system.dataset.toPyDataSet(ds):
        kg_in = float(row["kg_in"])
        kg_out = float(row["kg_out"])
        rows.append({
            "batch": row["batch_code"],
            "recipe": row["recipe"],
            "kgIn": kg_in,
            "kgOut": kg_out,
            "yieldPct": round(100.0 * kg_out / kg_in, 1),
            "finished": row["finished_at"] is not None,
        })
    return rows


def yield_series():
    """Batch yield percentages for the chart view."""
    return [
        {"batch": r["batch"], "yieldPct": r["yieldPct"]}
        for r in batches()
    ]


def history_row_count():
    """Total rows the PlantHistory provider has stored (tsdb_data)."""
    ds = system.db.runPrepQuery("SELECT count(*) AS n FROM tsdb_data", [], "PlantDB")
    return int(system.dataset.toPyDataSet(ds)[0]["n"])


def recent_history():
    """Most recent historized values, joined with their tag paths."""
    ds = system.db.runPrepQuery(
        "SELECT te.tag_path, d.value_double, d.quality, "
        "to_timestamp(d.time / 1000.0) AS t_stamp "
        "FROM tsdb_data d JOIN tsdb_te te ON te.id = d.tag_id "
        "ORDER BY d.time DESC LIMIT 20",
        [],
        "PlantDB",
    )
    return [
        {
            "tag": row["tag_path"],
            "value": round(float(row["value_double"]), 2) if row["value_double"] is not None else None,
            "quality": row["quality"],
            "stamp": str(row["t_stamp"]),
        }
        for row in system.dataset.toPyDataSet(ds)
    ]
