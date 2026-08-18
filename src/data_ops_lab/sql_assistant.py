from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SuggestedQuery:
    title: str
    sql: str
    rationale: str


def generate_starter_queries(schema: dict, keys: dict) -> list[SuggestedQuery]:
    queries: list[SuggestedQuery] = []

    for table_name, table_schema in schema.items():
        columns = [column["name"] for column in table_schema["columns"]]
        queries.append(
            SuggestedQuery(
                title=f"Row count for {table_name}",
                sql=f"select count(*) as row_count from {table_name};",  # noqa: S608 - reviewable suggestion text; never executed by this module
                rationale="Basic reconciliation query for validating loaded row volume.",
            )
        )
        numeric_columns = [
            column["name"]
            for column in table_schema["columns"]
            if column["semantic_type"] in {"number", "currency"}
        ]
        if numeric_columns:
            metrics = ",\n       ".join(f"sum({column}) as total_{column}" for column in numeric_columns[:4])
            queries.append(
                SuggestedQuery(
                    title=f"Numeric totals for {table_name}",
                    sql=f"select {metrics}\nfrom {table_name};",
                    rationale="Control totals help detect join fanout or export errors.",
                )
            )
        if columns:
            queries.append(
                SuggestedQuery(
                    title=f"Duplicate check for {table_name}",
                    sql=(
                        f"select {', '.join(columns[:3])}, count(*) as duplicate_count\n"
                        f"from {table_name}\n"
                        f"group by {', '.join(columns[:3])}\n"
                        "having count(*) > 1\n"
                        "order by duplicate_count desc;"
                    ),
                    rationale="Surfaces repeated business records using the first available identifying columns.",
                )
            )

    for relation in keys.get("foreign_keys", []):
        left = relation["from_table"]
        right = relation["to_table"]
        left_col = relation["from_column"]
        right_col = relation["to_column"]
        queries.append(
            SuggestedQuery(
                title=f"Validated join: {left} to {right}",
                sql=(
                    f"select l.*, r.* exclude ({right_col})\n"
                    f"from {left} as l\n"
                    f"left join {right} as r\n"
                    f"  on l.{left_col} = r.{right_col};"
                ),
                rationale="Uses detected key coverage to propose a BI-ready left join.",
            )
        )

    return queries


def render_queries_markdown(queries: list[SuggestedQuery]) -> str:
    sections = ["# SQL Assistant Suggestions", ""]
    for query in queries:
        sections.extend(
            [
                f"## {query.title}",
                query.rationale,
                "",
                "```sql",
                query.sql,
                "```",
                "",
            ]
        )
    return "\n".join(sections)
