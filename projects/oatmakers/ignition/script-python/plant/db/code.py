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
