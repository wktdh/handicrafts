import { mkdir, readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";

// Keep a real HTML entry point for every public category URL. This means a
// direct visit works even before an Nginx history-fallback rule is in place,
// and gives crawlers category-specific title, description and canonical tags.
const categories = [
  ["jewelry-accessories", "Jewelry & Accessories", "Explore one-of-a-kind handmade jewelry and accessories from independent makers."],
  ["clothing-shoes", "Clothing & Shoes", "Discover handmade clothing, embroidered pieces, leather goods, and unique shoes."],
  ["home-living", "Home & Living", "Find original handmade home decor, textiles, woodwork, and floral pieces."],
  ["weddings-parties", "Weddings & Parties", "Shop handmade wedding details, party decor, invitations, and celebration pieces."],
  ["toys-entertainment", "Toys & Entertainment", "Browse imaginative handmade toys, miniatures, and entertaining finds."],
  ["art-collectibles", "Art & Collectibles", "Collect original art, traditional crafts, and handmade pieces with a story."],
  ["craft-supplies-tools", "Craft Supplies & Tools", "Explore supplies and tools for your next handmade project."],
  ["vintage", "Vintage", "Discover distinctive vintage finds selected for their history and character."],
  ["bags-purses", "Bags & Purses", "Shop handmade bags, purses, textile accessories, and leather goods."],
  ["paper-party-supplies", "Paper & Party Supplies", "Find handmade stationery, paper goods, invitations, and party supplies."],
  ["pet-supplies", "Pet Supplies", "Discover thoughtful handmade goods made for pets and their people."],
  ["bath-beauty", "Bath & Beauty", "Shop handmade soap, candles, fragrance, and small daily rituals."],
  ["ceramics", "Ceramics", "Explore original handmade ceramics, pottery, clay art, and sculptural pieces."],
  ["textiles-fiber", "Textiles & Fiber Arts", "Discover woven, knitted, embroidered, and felted handmade creations."],
];

const escapeHtml = (value) =>
  value.replaceAll("&", "&amp;").replaceAll('"', "&quot;");

const indexHtml = await readFile(join("dist", "index.html"), "utf8");

await Promise.all(
  categories.map(async ([slug, label, description]) => {
    const url = `https://shouzuohub.com/categories/${slug}`;
    const title = `${label} | Shouzuo Hub Handmade Marketplace`;
    const html = indexHtml
      .replace(/<meta name="description" content="[^"]*" \/>/, `<meta name="description" content="${escapeHtml(description)}" />`)
      .replace(/<link rel="canonical" href="[^"]*" \/>/, `<link rel="canonical" href="${url}" />`)
      .replace(/<meta property="og:title" content="[^"]*" \/>/, `<meta property="og:title" content="${escapeHtml(title)}" />`)
      .replace(/<meta property="og:description" content="[^"]*" \/>/, `<meta property="og:description" content="${escapeHtml(description)}" />`)
      .replace(/<meta property="og:url" content="[^"]*" \/>/, `<meta property="og:url" content="${url}" />`)
      .replace(/<title>[^<]*<\/title>/, `<title>${escapeHtml(title)}</title>`);
    const directory = join("dist", "categories", slug);
    await mkdir(directory, { recursive: true });
    await writeFile(join(directory, "index.html"), html);
  }),
);

const standalonePages = [
  ["discover", "Discover Handmade | Shouzuo Hub", "Browse handmade pieces from independent makers."],
  ["seller/dashboard", "Seller Dashboard | Shouzuo Hub", "Manage your Shouzuo Hub shop, products, and orders."],
  ["shop", "Shop Page | Shouzuo Hub", "Explore the maker's shop and handmade collection."],
  ["community", "Creator Community | Shouzuo Hub", "Connect with independent makers, share ideas, and discuss handmade work."],
];

await Promise.all(
  standalonePages.map(async ([path, title, description]) => {
    const url = `https://shouzuohub.com/${path}/`;
    const html = indexHtml
      .replace(/<meta name="description" content="[^"]*" \/>/, `<meta name="description" content="${escapeHtml(description)}" />`)
      .replace(/<link rel="canonical" href="[^"]*" \/>/, `<link rel="canonical" href="${url}" />`)
      .replace(/<meta property="og:title" content="[^"]*" \/>/, `<meta property="og:title" content="${escapeHtml(title)}" />`)
      .replace(/<meta property="og:description" content="[^"]*" \/>/, `<meta property="og:description" content="${escapeHtml(description)}" />`)
      .replace(/<meta property="og:url" content="[^"]*" \/>/, `<meta property="og:url" content="${url}" />`)
      .replace(/<title>[^<]*<\/title>/, `<title>${escapeHtml(title)}</title>`);
    const directory = join("dist", ...path.split("/"));
    await mkdir(directory, { recursive: true });
    await writeFile(join(directory, "index.html"), html);
  }),
);
