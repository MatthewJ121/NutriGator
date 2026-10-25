from sqlalchemy import inspect, text
import database
import main

database.engine.echo = False


def main():
    if not database.DATABASE_URL:
        print("DATABASE_URL is missing. Copy env.backend.example to .env.backend and fill it in.")
        return

    before = set(inspect(database.engine).get_table_names())
    database.Base.metadata.create_all(database.engine)
    after = set(inspect(database.engine).get_table_names())

    for table in sorted(after - before):
        print(f"Created table {table}")

    meal_columns = [column["name"] for column in inspect(database.engine).get_columns("Meals")]
    if "consumed_at" not in meal_columns:
        with database.engine.begin() as connection:
            connection.execute(text('ALTER TABLE "Meals" ADD COLUMN consumed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()'))
        print('Added consumed_at column to "Meals"')

    for table in database.Base.metadata.sorted_tables:
        existing = {column["name"] for column in inspect(database.engine).get_columns(table.name)}
        missing = [column.name for column in table.columns if column.name not in existing]
        if missing:
            print(f'Table "{table.name}" in Neon is missing columns: {", ".join(missing)}')
        else:
            print(f'Table "{table.name}" looks good')


if __name__ == "__main__":
    main()
