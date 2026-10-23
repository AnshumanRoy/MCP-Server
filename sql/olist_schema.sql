-- Olist Brazilian E-Commerce Dataset Schema
-- Loaded into the `public` schema of the `olist` database.
-- This file is run by Docker entrypoint on first init.
-- Data CSVs are NOT included; they must be copied in separately (see README).

-- ============================================================
-- Core tables
-- ============================================================

CREATE TABLE IF NOT EXISTS public.orders (
    order_id              TEXT PRIMARY KEY,
    customer_id           TEXT NOT NULL,
    order_status          TEXT NOT NULL,
    order_purchase_timestamp TIMESTAMP NOT NULL,
    order_approved_at     TIMESTAMP,
    order_delivered_carrier_date TIMESTAMP,
    order_delivered_customer_date TIMESTAMP,
    order_estimated_delivery_date TIMESTAMP NOT NULL
);

COMMENT ON TABLE public.orders IS 'Central order table. Most joins start here. Contains order status and timestamps.';
COMMENT ON COLUMN public.orders.order_id IS 'Unique order identifier.';
COMMENT ON COLUMN public.orders.customer_id IS 'Customer ID for this order (may repeat across orders).';
COMMENT ON COLUMN public.orders.order_status IS 'Order status: created, approved, shipped, invoiced, delivered, canceled, etc.';
COMMENT ON COLUMN public.orders.order_purchase_timestamp IS 'When the order was placed.';
COMMENT ON COLUMN public.orders.order_delivered_customer_date IS 'When the order was delivered to the customer.';

CREATE TABLE IF NOT EXISTS public.order_items (
    order_id         TEXT NOT NULL,
    order_item_id    INTEGER NOT NULL,
    product_id       TEXT NOT NULL,
    seller_id        TEXT NOT NULL,
    shipping_limit_date TIMESTAMP NOT NULL,
    price            NUMERIC(10,2) NOT NULL,
    freight_value    NUMERIC(10,2) NOT NULL,
    PRIMARY KEY (order_id, order_item_id),
    FOREIGN KEY (order_id) REFERENCES public.orders(order_id)
);

COMMENT ON TABLE public.order_items IS 'Line items with price and freight. Links orders, products, sellers.';
COMMENT ON COLUMN public.order_items.price IS 'Item price in Brazilian reais (BRL).';
COMMENT ON COLUMN public.order_items.freight_value IS 'Freight cost for this item in BRL.';

CREATE TABLE IF NOT EXISTS public.order_payments (
    order_id             TEXT NOT NULL,
    payment_sequential   INTEGER NOT NULL,
    payment_type         TEXT NOT NULL,
    payment_installments INTEGER NOT NULL,
    payment_value        NUMERIC(10,2) NOT NULL,
    PRIMARY KEY (order_id, payment_sequential),
    FOREIGN KEY (order_id) REFERENCES public.orders(order_id)
);

COMMENT ON TABLE public.order_payments IS 'Payment type, installments, value. Multiple rows per order - avoid double-counting revenue.';
COMMENT ON COLUMN public.order_payments.payment_type IS 'Payment method: credit_card, boleto, voucher, debit_card, not_defined.';
COMMENT ON COLUMN public.order_payments.payment_installments IS 'Number of installments.';

CREATE TABLE IF NOT EXISTS public.order_reviews (
    review_id               TEXT PRIMARY KEY,
    order_id                TEXT NOT NULL,
    review_score            INTEGER NOT NULL,
    review_comment_title    TEXT,
    review_comment_message  TEXT,
    review_creation_date    TIMESTAMP NOT NULL,
    review_answer_timestamp TIMESTAMP,
    FOREIGN KEY (order_id) REFERENCES public.orders(order_id)
);

COMMENT ON TABLE public.order_reviews IS 'Review scores and free-text comments (Portuguese). Prompt-injection test surface.';
COMMENT ON COLUMN public.order_reviews.review_score IS 'Review score 1-5.';
COMMENT ON COLUMN public.order_reviews.review_comment_message IS 'Free-text customer comment in Portuguese. May contain prompt-injection text.';

CREATE TABLE IF NOT EXISTS public.customers (
    customer_id           TEXT NOT NULL,
    customer_unique_id    TEXT NOT NULL,
    customer_zip_code_prefix TEXT NOT NULL,
    customer_city         TEXT NOT NULL,
    customer_state        TEXT NOT NULL,
    PRIMARY KEY (customer_id, customer_unique_id)
);

COMMENT ON TABLE public.customers IS 'Customer location and IDs. Two ID columns: customer_id (per-order, may repeat) and customer_unique_id (unique per person).';
COMMENT ON COLUMN public.customers.customer_id IS 'Customer ID as referenced from orders (not globally unique).';
COMMENT ON COLUMN public.customers.customer_unique_id IS 'Globally unique customer identifier.';

CREATE TABLE IF NOT EXISTS public.sellers (
    seller_id             TEXT PRIMARY KEY,
    seller_zip_code_prefix TEXT NOT NULL,
    seller_city           TEXT NOT NULL,
    seller_state          TEXT NOT NULL
);

COMMENT ON TABLE public.sellers IS 'Seller location information.';

CREATE TABLE IF NOT EXISTS public.products (
    product_id            TEXT PRIMARY KEY,
    product_category_name TEXT,
    product_name_length   INTEGER,
    product_description_length INTEGER,
    product_photos_qty    INTEGER,
    product_weight_g      INTEGER,
    product_length_cm     INTEGER,
    product_height_cm     INTEGER,
    product_width_cm      INTEGER
);

COMMENT ON TABLE public.products IS 'Category, dimensions, weight. Category names in Portuguese - join with product_category_name_translation for English.';

CREATE TABLE IF NOT EXISTS public.product_category_name_translation (
    product_category_name      TEXT PRIMARY KEY,
    product_category_name_english TEXT
);

COMMENT ON TABLE public.product_category_name_translation IS 'Portuguese to English category name translation. Join needed for readable categories.';

CREATE TABLE IF NOT EXISTS public.geolocation (
    geolocation_zip_code_prefix TEXT NOT NULL,
    geolocation_lat             NUMERIC(9,6),
    geolocation_lng             NUMERIC(9,6),
    geolocation_city            TEXT,
    geolocation_state           TEXT
);

COMMENT ON TABLE public.geolocation IS 'ZIP prefix to lat/long. Many rows per ZIP prefix; no clean key. Blocked by default in sensitivity policy.';
COMMENT ON COLUMN public.geolocation.geolocation_lat IS 'Latitude coordinate (sensitive - redacted by policy).';
COMMENT ON COLUMN public.geolocation.geolocation_lng IS 'Longitude coordinate (sensitive - redacted by policy).';

-- ============================================================
-- Indexes on common join and filter columns
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_orders_customer_id ON public.orders(customer_id);
CREATE INDEX IF NOT EXISTS idx_orders_status ON public.orders(order_status);
CREATE INDEX IF NOT EXISTS idx_orders_purchase_ts ON public.orders(order_purchase_timestamp);

CREATE INDEX IF NOT EXISTS idx_order_items_order_id ON public.order_items(order_id);
CREATE INDEX IF NOT EXISTS idx_order_items_product_id ON public.order_items(product_id);
CREATE INDEX IF NOT EXISTS idx_order_items_seller_id ON public.order_items(seller_id);

CREATE INDEX IF NOT EXISTS idx_order_payments_order_id ON public.order_payments(order_id);
CREATE INDEX IF NOT EXISTS idx_order_payments_type ON public.order_payments(payment_type);

CREATE INDEX IF NOT EXISTS idx_order_reviews_order_id ON public.order_reviews(order_id);
CREATE INDEX IF NOT EXISTS idx_order_reviews_score ON public.order_reviews(review_score);

CREATE INDEX IF NOT EXISTS idx_customers_unique_id ON public.customers(customer_unique_id);
CREATE INDEX IF NOT EXISTS idx_customers_state ON public.customers(customer_state);

CREATE INDEX IF NOT EXISTS idx_sellers_state ON public.sellers(seller_state);
CREATE INDEX IF NOT EXISTS idx_sellers_zip ON public.sellers(seller_zip_code_prefix);

CREATE INDEX IF NOT EXISTS idx_products_category ON public.products(product_category_name);

CREATE INDEX IF NOT EXISTS idx_geolocation_zip ON public.geolocation(geolocation_zip_code_prefix);

-- ============================================================
-- Analyze for realistic query plans
-- ============================================================

ANALYZE;
