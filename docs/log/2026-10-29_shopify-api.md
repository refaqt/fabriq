# 2026-10-29 — Can a program edit our Shopify shop?

**Role(s):** software, marketing

## What happened

We asked if a program can change all the content of our Shopify webshop. The answer is
yes, for almost everything. Shopify has an official interface for programs, the
**Admin API**. A script can change product texts, pictures and prices. No code was
written yet.

This answer comes from Shopify's public documentation. The fabriq code has no Shopify
link today.

What the API can change:

| Content | Can the API change it? |
| ------- | ---------------------- |
| Product titles, descriptions, tags, product type, vendor | Yes |
| Product pictures and videos (add, replace, reorder, alt text) | Yes |
| Prices and "compare at" prices (the old, crossed-out price), per variant | Yes |
| Variants (size, colour), SKU codes (stock numbers), barcodes, weight | Yes |
| Stock levels per location | Yes |
| Collections (product groups) | Yes |
| Search engine text (SEO title and description), web addresses of pages | Yes |
| Extra custom fields (Shopify calls them "metafields") | Yes |
| Pages, blog posts, navigation menus | Yes |
| Translations into other languages | Yes |
| Different prices per country (Shopify "Markets" price lists) | Yes |
| Discounts and discount codes | Yes |
| Theme files (the shop design) | Yes, with the right access. A mistake here breaks the live shop. |

What the API cannot change, or only in part:

- Checkout pages. Only small changes, mostly on the Shopify Plus plan.
- Payment providers, billing and some account settings. These stay in the Shopify admin
  screens.
- Shopify limits how many changes per second a script can make. Large jobs work, but
  they take time. Shopify has a "bulk operations" mode for them.

How access works:

1. Create an app for our own shop (a "custom app") in the Shopify **Dev Dashboard**. The
   old way, inside the shop admin, is being phased out.
2. Give the app only the rights it needs, for example `read_products`, `write_products`,
   `write_content` and `write_inventory`.
3. Shopify gives a secret key (an "access token"). Treat it like a password. Never put it
   in the code repository.
4. Use the **GraphQL Admin API**. Shopify calls the older "REST" version legacy.

## Open Questions

- What do we want to automate first? For example: update all prices from our price
  list, or rewrite the product descriptions.

## Next Steps

- Test on a development store or a copy of the shop first, never on the live shop.
- Export all products to a CSV file before the first bulk change, as a backup.
- Before a large price change, ask the accountant to check how VAT is shown. In Belgium,
  consumer prices must include VAT.
