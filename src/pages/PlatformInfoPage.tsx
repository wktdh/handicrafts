import { ArrowLeft } from "lucide-react";
import type { ReactNode } from "react";

type FooterPage =
  | "about"
  | "seller-guide"
  | "returns"
  | "custom-orders"
  | "disputes"
  | "shipping"
  | "privacy"
  | "terms"
  | "cookies"
  | "help";

type PageContent = {
  eyebrow: string;
  title: string;
  intro: string;
  singleLayer?: boolean;
  sections: { title: string; content: ReactNode }[];
};

const pages: Record<FooterPage, PageContent> = {
  about: {
    eyebrow: "ABOUT SHOUZUO HUB",
    title: "About Shouzuo Hub",
    intro: "Made by hand, shared with the world.",
    singleLayer: true,
    sections: [
      { title: "Who we are", content: "Shouzuo Hub is a Shenzhen-based cross-border marketplace for original handmade work. We connect independent makers with people around the world who value thoughtful objects, personal expression, and the warmth of work made by hand." },
      { title: "What we believe", content: <ul><li><strong>True to the handmade:</strong> We champion original work over factory-made repetition. The marks, textures, and small variations in a piece are part of its maker’s signature.</li><li><strong>Eastern craft in living form:</strong> From heritage techniques and folk crafts to contemporary independent design, we hope more people can discover the depth, detail, and evolving creativity of Chinese craftsmanship.</li><li><strong>Connection without borders:</strong> We help makers share their work beyond geography and language, while helping collectors discover objects with culture, character, and a story.</li><li><strong>Warmth for everyday life:</strong> We believe handmade objects can bring a sense of ritual and comfort to everyday routines, simply because they were made with care.</li></ul> },
      { title: "Why we began", content: <><p>In a world full of standardised goods, handmade work offers something increasingly rare: honest materials, individual imagination, and time made visible. Yet many skilled makers and small creative studios have long been limited by distance and access to global audiences.</p><p>Shouzuo Hub began with a simple purpose: build a bridge for craftsmanship and let beautiful work travel further. We bring together handmade pieces ranging from heritage-inspired craft to modern original design, from quiet everyday objects to expressive works of art.</p><p>By connecting makers and buyers across borders, we hope every act of making can be seen, valued, and carried into someone else’s daily life.</p></> },
      { title: "Our commitment", content: "We are building a thoughtful marketplace around originality, clear communication, and respect for the people behind each piece. Shouzuo Hub exists to help makers grow sustainably and to help buyers choose with confidence, curiosity, and care." },
    ],
  },
  "seller-guide": {
    eyebrow: "SELL WITH US", title: "Sell original work with us", intro: "Shouzuo Hub is for makers, independent designers, and small creative businesses bringing original handmade work to customers around the world.",
    sections: [
      { title: "Who can join", content: "We welcome individual makers, independent designers, home studios, heritage-craft practitioners, sole proprietors, and small businesses whose work is centred on original handmade creation. Small-batch collaborative production may be accepted when it is disclosed clearly. Reworked and upcycled original pieces are also welcome." },
      { title: "What we do not accept", content: "Shouzuo Hub is not for reselling, unaltered wholesale goods, dropshipping without active creation, factory-made products presented as handmade, or large-scale industrial factories. We also prohibit counterfeit, infringing, unlicensed, dangerous, illegal, or restricted goods." },
      { title: "Verification and handmade review", content: "Individual makers need identity verification; registered businesses need their business registration. Your cross-border payout account must be verified in the same name as the joining entity. To review originality, we may ask for genuine product photos, making-process images, and studio or workbench photos. Sellers must use their own images and designs, respect intellectual-property rights, disclose any production partner on the listing, and meet applicable product-safety requirements for their destination markets. Complete applications are usually reviewed within 1–2 business days; incomplete or unclear applications can be supplemented and resubmitted." },
      { title: "Fees", content: "There is no annual fee, security deposit, or listing fee. We charge a 5% platform commission only on a successful order’s total amount, including the item price and buyer-paid shipping. If an order is refunded, the related platform commission is returned. Payment gateway, currency-conversion, and cash-out fees are charged by the relevant third-party provider, not by Shouzuo Hub. Optional promotional placements may carry a separate activity fee only when you choose to participate." },
      { title: "Payouts and settlement", content: "An order becomes completed when the buyer confirms delivery, or when its tracking record shows Delivered. Completed orders enter a 3-business-day hold before moving into your available balance. New sellers may have a longer hold during their first 90 days while risk checks are in place. Weekly payout is the default, initiated each Monday. Sellers can choose daily, weekly, biweekly (every other Monday), or monthly payout. The minimum payout is US$25; smaller available balances roll over. Orders with open returns or disputes can remain on hold until the case is resolved." },
      { title: "Receiving your funds", content: "After the 5% platform commission and applicable third-party payment fees are deducted, funds are paid to the cross-border payout account linked to your seller profile, such as LianLian, PingPong, or WorldFirst where supported. You are responsible for withdrawing or converting funds through that provider and for meeting your own tax-reporting obligations. Exchange rates and conversion fees are set by the payout provider; Shouzuo Hub does not bear exchange-rate gains or losses." },
    ],
  },
  returns: { eyebrow: "RETURNS & REFUNDS", title: "Returns and refunds", intro: "Shouzuo Hub is home to independent sellers. Each seller sets the return, exchange, and refund policy for their own listings.", sections: [{ title: "The item policy comes first", content: "Before ordering, review the return, exchange, and refund window, eligibility, return address, and return-shipping terms on the item and shop pages. Policies can differ by seller, item, and destination. The policy clearly shown on the listing applies first." }, { title: "Making a request", content: "Start a request from your order, describe the issue, and include helpful photos, video, or delivery evidence. The seller will review the request under their stated policy. When a return is approved, follow the seller’s return instructions. Your order status will update after the seller confirms receipt or agrees to a refund without return." }, { title: "Handmade and custom items", content: "Made-to-order, personalised, or items that cannot be resold may not be eligible for a change-of-mind return. This does not limit remedies for damaged, materially misdescribed, or otherwise non-conforming items where applicable law requires them. See the seller’s policy and your local consumer-protection rights." }, { title: "If you cannot agree", content: "We encourage buyers and sellers to use order messages and keep a clear record. If the issue remains unresolved, submit an order support request with the item page, messages, tracking information, and relevant evidence for platform review." }] },
  "custom-orders": { eyebrow: "CUSTOM ORDERS", title: "Custom orders", intro: "Confirm the design, price, production time, and delivery schedule with the maker before you order.", sections: [{ title: "Before you buy", content: "Share the size, color, materials, wording, references, and other requirements. Changes after production begins may affect the price and delivery date." }] },
  disputes: { eyebrow: "DISPUTE RESOLUTION", title: "Dispute resolution", intro: "We encourage customers and makers to resolve order questions through the order conversation first.", sections: [{ title: "Need more help?", content: "If you cannot reach an agreement, submit a support request with the order details, messages, photos, and tracking information that explain the issue." }] },
  shipping: { eyebrow: "SHIPPING & DUTIES", title: "Shipping and duties", intro: "Shouzuo Hub brings together independent makers, so delivery details are set by the seller and can vary by item and destination.", sections: [{ title: "Where we ship", content: "Shouzuo Hub supports cross-border delivery to countries in Europe and North America. Check the item page and checkout for the destinations available for a particular listing." }, { title: "Making, dispatch, and cost", content: "Each seller sets their own production time, dispatch estimate, shipping method, shipping cost, and free-shipping threshold. SF International is the default delivery service unless the seller states a different carrier on the item page. Review the listing’s processing time and delivery cost before ordering." }, { title: "Tracking and delivery", content: "When tracking is available, the seller will add the tracking details to your order after dispatch. Delivery dates are estimates and may be affected by customs checks, weather, public holidays, and local carrier operations." }, { title: "Duties and taxes", content: "Your destination may charge import duties, VAT, sales tax, or customs-clearance fees. Where applicable charges are collected at checkout, they will appear in your order total. Charges that are not shown at checkout may be collected from the recipient during customs clearance or delivery, in accordance with local rules." }] },
  privacy: { eyebrow: "PRIVACY POLICY", title: "Privacy policy", intro: "We use personal information only to operate and protect the marketplace and to support your orders.", sections: [{ title: "Your information", content: "We process account, contact, delivery, order, and support information to provide our services, prevent abuse, and meet legal obligations. We do not sell personal information." }] },
  terms: { eyebrow: "TERMS OF SERVICE", title: "Terms of service", intro: "These terms explain how customers, makers, and Shouzuo Hub use the marketplace.", sections: [{ title: "Marketplace role", content: "Shouzuo Hub provides tools for product discovery, communication, and transactions. Makers are responsible for their listings, fulfillment, delivery, and after-sales service unless otherwise required by law." }] },
  cookies: { eyebrow: "COOKIE POLICY", title: "Cookie policy", intro: "Cookies help keep you signed in and enable essential marketplace features.", sections: [{ title: "Essential cookies", content: "We use essential cookies for security, sessions, and core website functionality. Optional analytics or advertising cookies will be explained before they are enabled where consent is required." }] },
  help: { eyebrow: "HELP CENTER", title: "Help center", intro: "Find help with your account, orders, shipping, and support requests.", sections: [{ title: "Need assistance?", content: "Use the messages area to contact a maker about an item or order. For platform, payment, or account issues, create a support request from Messages." }] },
};

export default function PlatformInfoPage({ page, onBack }: { page: FooterPage; onBack: () => void }) {
  const current = pages[page];
  const content = <><header className="platform-info-heading"><p className="eyebrow">{current.eyebrow}</p><h1>{current.title}</h1>{current.intro && <p>{current.intro}</p>}</header><div className="platform-info-sections">{current.sections.map((section) => <section key={section.title}>{section.title && <h2>{section.title}</h2>}<div>{section.content}</div></section>)}</div></>;
  return <main className="container page section platform-info-page"><button className="back" onClick={onBack}><ArrowLeft size={18} />Back</button>{current.singleLayer ? <section className="platform-info-single-layer">{content}</section> : content}</main>;
}
