--Represent individual assets
CREATE TABLE "assets"(
    "id" INTEGER,
    "ticker" TEXT NOT NULL UNIQUE,
    "name" TEXT NOT NULL,
    "asset_class" TEXT CHECK ("asset_class" IN ('Equity', 'Bonds', 'Cash', 'Crypto')),
    "currency" TEXT NOT NULL CHECK("currency" IN ('HKD', 'USD', 'GBP')),
    PRIMARY KEY ("id")
);


--Represent assets allocation targets at different age
CREATE TABLE "glide_path"(
    "id" INTEGER,
    "asset_id" INTEGER NOT NULL,
    "age" INTEGER,
    "milestone" NUMERIC,
    "target_percent" NUMERIC NOT NULL,
    PRIMARY KEY ("id"),
    FOREIGN KEY("asset_id") REFERENCES "assets"("id") ON DELETE CASCADE
);


--Represent trasanctions in the portfolio
CREATE TABLE "transactions"(
    "id" INTEGER,
    "asset_id" INTEGER NOT NULL,
    "date" TEXT NOT NULL DEFAULT CURRENT_DATE,
    "type" TEXT CHECK("type" in ('BUY', 'SELL')),
    "shares" NUMERIC NOT NULL,
    "price_per_share" NUMERIC NOT NULL,
    PRIMARY KEY ("id"),
    FOREIGN KEY("asset_id") REFERENCES "assets"("id") ON DELETE CASCADE
);


--Represent market values of current portfolio
CREATE TABLE "market_prices"(
    "id" INTEGER,
    "asset_id" INTEGER NOT NULL UNIQUE,
    "current_price" REAL NOT NULL,
    "last_updated" TEXT DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY ("id"),
    FOREIGN KEY("asset_id") REFERENCES "assets"("id") ON DELETE CASCADE
);


-- Create indexes to speed common searches
CREATE INDEX "idx_transactions_asset_id" ON "transactions"("asset_id");
CREATE INDEX "idx_transactions_date" ON "transactions"("date");
CREATE INDEX "idx_glide_path_age" ON "glide_path"("age");


-- View: Summarize current holdings and their market value
CREATE VIEW "portfolio_summary" AS
SELECT
    "assets"."ticker",
    SUM("transactions"."shares") AS "total_shares",
    ROUND("market_prices"."current_price", 2) AS "current_price",
    ROUND(SUM("transactions"."shares") * "market_prices"."current_price", 2) AS "market_value_hkd",
    "market_prices"."last_updated"
FROM "assets"
JOIN "transactions" ON "assets"."id" = "transactions"."asset_id"
JOIN "market_prices" ON "assets"."id" = "market_prices"."asset_id"
GROUP BY "assets"."ticker"
HAVING "total_shares" > 0;
