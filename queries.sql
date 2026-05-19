-- View all assets and their associated currency
SELECT "ticker", "name", "currency" FROM "assets";

-- View your "Strategy": What are my targets for Age 30?
SELECT "ticker", "target_percent"
FROM "assets"
JOIN "glide_path" ON "assets"."id" = "glide_path"."asset_id"
WHERE "age" = 30 AND "target_percent" != 0;

-- View "History": List all buys recorded so far
SELECT "date", "ticker", "shares", "price_per_share"
FROM "transactions"
JOIN "assets" ON "transactions"."asset_id" = "assets"."id"
WHERE "type" = 'BUY';

-- View the current market value of all holdings
-- (Shares x Current Price) Using the created view "portfolio_summary"
SELECT * FROM "portfolio_summary";


-- Add a new asset (e.g., Vanguard World)
-- Note: Use the Yahoo Finance ticker format for the Python engine
INSERT INTO "assets" ("ticker", "name", "asset_class", "currency")
VALUES ('VWRA.L', 'Vanguard FTSE All-World', 'Equity', 'USD');

-- Define a Glide Path target for a specific age
-- Linking VWRA (id: 1) to a 80% target for Age 30
INSERT INTO "glide_path" ("asset_id", "age", "target_percent")
VALUES (1, 30, 0.80);

-- Record an initial purchase (Transaction)
INSERT INTO "transactions" ("asset_id", "type", "shares", "price_per_share")
VALUES (1, 'BUY', 50, 115.20);

-- Seed the market price table with the purchase price
INSERT INTO "market_prices" ("asset_id", "current_price")
VALUES (1, 115.20);

-- Remove a specific transaction (e.g., a mistaken entry)
DELETE FROM "transactions"
WHERE "id" = 101;

-- Remove an asset and all its related data (Glide Path, Prices, Transactions)
DELETE FROM "assets"
WHERE "ticker" = 'QQQ';
