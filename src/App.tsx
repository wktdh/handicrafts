import {
  useEffect,
  lazy,
  useMemo,
  useRef,
  Suspense,
  useState,
  type FormEvent,
  type MouseEvent,
} from "react";
import {
  ArrowLeft,
  ArrowDown,
  ArrowDownLeft,
  ArrowDownRight,
  ArrowRight,
  ArrowUp,
  ArrowUpLeft,
  ChevronDown,
  BadgePercent,
  Bell,
  Check,
  ChevronRight,
  ChevronUp,
  CreditCard,
  Globe2,
  Heart,
  LogOut,
  MapPin,
  ImagePlus,
  LoaderCircle,
  Maximize2,
  Menu,
  MessageCircle,
  Minimize2,
  Minus,
  Package,
  Palette,
  Plus,
  Search,
  Send,
  Settings2,
  ShoppingBag,
  Smile,
  SlidersHorizontal,
  Star,
  Store,
  Crosshair,
  Pipette,
  Truck,
  UserRound,
  Video,
  X,
  type LucideIcon,
} from "lucide-react";
import {
  playNewBuyerMessageChime,
  unlockNewBuyerMessageChime,
} from "./audio/newBuyerMessageChime";
import ceramicCupImage from "./images/ceramic-cup.jpg";
import moonstoneEarringsImage from "./images/moonstone-earrings.jpg";
import woolTableRunnerImage from "./images/wool-table-runner.jpg";
import springCardImage from "./images/spring-card.jpg";
import vintageVaseImage from "./images/vintage-vase.jpg";
import shopBannerImage from "./images/shop-banner.jpg";
import shopAvatarImage from "./images/shop-avatar.jpg";
import defaultAvatarImage from "./images/default_ avatar.jpeg";
import shouzuoWordmarkImage from "./images/shouzuo-wordmark-orange-s-white-text.png";

// The colour picker is only needed inside the brand-site editor. Loading it
// after the editor control is opened keeps it out of the primary route chunk.
const LazyHexAlphaColorPicker = lazy(() => import("./components/HexAlphaColorPicker"));
const LazyPlatformInfoPage = lazy(() => import("./pages/PlatformInfoPage"));
const LazyAdminConsole = lazy(() => import("./pages/admin/AdminConsole"));
const LazySellerAiAssistant = lazy(
  () => import("./pages/seller/SellerAiAssistant"),
);
const LazySellerProductEditor = lazy(
  () => import("./pages/seller/SellerProductEditor"),
);
const LazySellerProductList = lazy(
  () => import("./pages/seller/SellerProductList"),
);
const LazySellerInventoryPage = lazy(
  () => import("./pages/seller/SellerInventoryPage"),
);
const LazySellerFulfillmentPage = lazy(
  () => import("./pages/seller/SellerFulfillmentPage"),
);
const LazySellerReviewsPage = lazy(
  () => import("./pages/seller/SellerReviewsPage"),
);
const LazySellerShippingPage = lazy(
  () => import("./pages/seller/SellerShippingPage"),
);
const LazySellerServiceManagement = lazy(
  () => import("./pages/seller/SellerServiceManagement"),
);
const LazySellerActivityOperations = lazy(
  () => import("./pages/seller/SellerActivityOperations"),
);
const LazyFinanceCenter = lazy(
  () => import("./pages/seller/FinanceCenter"),
);
const LazySellerPromotionsPage = lazy(
  () => import("./pages/seller/SellerPromotionsPage"),
);
const LazySellerSettingsPage = lazy(
  () => import("./pages/seller/SellerSettingsPage"),
);
const LazySellerBrandSitePage = lazy(
  () => import("./pages/seller/SellerBrandSitePage"),
);
const LazyDataAdvisor = lazy(
  () => import("./pages/seller/DataAdvisor"),
);
const LazyBrandSitePreview = lazy(
  () => import("./pages/seller/BrandSitePreview"),
);
const LazyBrandSiteBuilder = lazy(
  () => import("./pages/seller/BrandSiteBuilder"),
);
const LazyPublicBrandSite = lazy(
  () => import("./pages/buyer/PublicBrandSite"),
);
const LazyProductDetail = lazy(
  () => import("./pages/buyer/ProductDetail"),
);
const LazyShopPage = lazy(
  () => import("./pages/buyer/ShopPage"),
);
const LazyAccountSecurity = lazy(
  () =>
    import("./pages/account/AccountPages").then((module) => ({
      default: module.AccountSecurity,
    })),
);
const LazyProfileSettings = lazy(
  () =>
    import("./pages/account/AccountPages").then((module) => ({
      default: module.ProfileSettings,
    })),
);
const LazyCreatorCommunity = lazy(
  () => import("./pages/community/CreatorCommunity"),
);
const LazyNotificationCenter = lazy(
  () => import("./pages/buyer/NotificationCenter"),
);
const LazyFavoritesPage = lazy(
  () =>
    import("./pages/buyer/SavedPages").then((module) => ({
      default: module.FavoritesPage,
    })),
);
const LazyFollowingShops = lazy(
  () =>
    import("./pages/buyer/SavedPages").then((module) => ({
      default: module.FollowingShops,
    })),
);
const LazyShippingModal = lazy(
  () => import("./pages/orders/ShippingModal"),
);
const LazyOrdersPage = lazy(
  () => import("./pages/orders/OrdersPage"),
);
const LazyMessagesPage = lazy(
  () => import("./pages/messages/MessagesPage"),
);

// Seller registration and product publishing must use the same canonical
// operating-category list. Legacy discovery categories remain supported for
// existing catalogue records and homepage navigation.
const SELLER_OPERATING_CATEGORIES = [
  "布艺缝纫",
  "黏土&塑形",
  "滴胶&树脂",
  "编织",
  "木质&木艺",
  "皮具",
  "首饰",
  "陶艺陶瓷",
  "刺绣",
  "花艺干花",
  "香薰蜡烛 & 香氛",
  "古风国风",
  "绘画肌理",
  "纸品文创",
  "宠物专属",
  "微缩景观",
  "羊毛毡",
  "皂类",
  "非遗",
] as const;
type SellerOperatingCategory = (typeof SELLER_OPERATING_CATEGORIES)[number];
type Category = string;
export type OrderStatus =
  "待付款" | "待发货" | "运输中" | "待收货" | "已完成" | "已取消";
type ProductVariant = {
  name: string;
  values: string[];
  valueImages?: Record<string, string>;
  valueAssetIds?: Record<string, string>;
};
type ProductSku = {
  id: string;
  optionValues: Record<string, string>;
  stock: number;
  code?: string;
  price?: number;
  status?: "active" | "disabled";
};
type ShopPromotionType =
  "full_reduction" | "full_discount" | "coupon" | "limited_time";
type ShopPromotion = {
  id: number;
  type?: ShopPromotionType;
  threshold: number;
  discount?: number;
  rate?: number;
  startsAt?: string;
  endsAt?: string;
};
type ReturnPolicy = {
  acceptsReturns: boolean;
  windowDays: number;
  recipientName: string;
  recipientPhone: string;
  address: string;
  instructions: string;
};
// These are original platform themes.  Their visual language is inspired by
// well-known storefront patterns, but they do not include third-party theme
// code, names, imagery, or assets.
type BrandSiteTemplate = "dawn" | "craft" | "prestige";
type BrandSiteSectionId =
  | "announcement"
  | "header"
  | "hero"
  | "story"
  | "collection"
  | "columns"
  | "maker"
  | "services"
  | "promise"
  | "newsletter"
  | "image-text"
  | "testimonials"
  | "faq"
  | "footer";
type BrandSiteSection = {
  id: BrandSiteSectionId;
  label: string;
  title: string;
  content: string;
  buttonLabel?: string;
  enabled: boolean;
  imageUrl?: string;
  productIds?: string[];
  backgroundColor?: string;
  textColor?: string;
  buttonColor?: string;
  navLabels?: string[];
  navLinks?: string[];
  heroContentPosition?:
    | "top-left"
    | "top-center"
    | "top-right"
    | "center-left"
    | "center"
    | "center-right"
    | "bottom-left"
    | "bottom-center"
    | "bottom-right";
};
type BrandSiteConfig = {
  enabled: boolean;
  template: BrandSiteTemplate;
  siteName: string;
  tagline: string;
  themeColor: string;
  logoUrl?: string;
  domain: string;
  status: "draft" | "published";
  sections?: BrandSiteSection[];
};
const brandSiteTemplateSections: Record<BrandSiteTemplate, BrandSiteSection[]> =
  {
    dawn: [
      {
        id: "announcement",
        label: "公告栏",
        title: "满 ¥299 享免邮",
        content: "欢迎来到我们的手作商店",
        enabled: true,
      },
      {
        id: "header",
        label: "导航栏",
        title: "作品　关于　联系",
        content: "",
        enabled: true,
      },
      {
        id: "hero",
        label: "首屏横幅",
        title: "为日常挑选一件好作品",
        content: "简洁呈现每一件认真制作的手作，让访客更快找到喜欢的作品。",
        buttonLabel: "浏览作品",
        enabled: true,
      },
      {
        id: "collection",
        label: "作品陈列",
        title: "当季精选",
        content: "从店铺已上架的作品中，展示值得被看见的创作。",
        buttonLabel: "查看全部作品",
        enabled: true,
      },
      {
        id: "story",
        label: "富文本",
        title: "由手作，为日常",
        content: "每一件作品都从真实的材料、耐心的手工与对日常的想象开始。",
        buttonLabel: "了解更多",
        enabled: true,
      },
      {
        id: "columns",
        label: "多列内容",
        title: "关于我们的创作",
        content: "认真选材 · 手工制作 · 用心包装",
        enabled: true,
      },
      {
        id: "newsletter",
        label: "订阅邀请",
        title: "新品通知",
        content: "留下邮箱，第一时间知道新品与补货。",
        buttonLabel: "订阅更新",
        enabled: true,
      },
      {
        id: "footer",
        label: "页脚",
        title: "认真制作，慢慢相遇",
        content: "作品 · 关于我们 · 定制说明 · 配送与退货",
        enabled: true,
      },
    ],
    craft: [
      {
        id: "header",
        label: "导航栏",
        title: "作品　关于　联系",
        content: "",
        enabled: true,
      },
      {
        id: "hero",
        label: "首屏横幅",
        title: "走进创作者的工作室",
        content: "看见材料、工艺与每一次耐心完成。",
        buttonLabel: "查看创作过程",
        enabled: true,
      },
      {
        id: "maker",
        label: "创作者介绍",
        title: "一间专注手作的工作室",
        content: "从灵感到成品，坚持用真诚的工艺回应每一份期待。",
        enabled: true,
      },
      {
        id: "services",
        label: "定制服务",
        title: "为你制作独一无二的作品",
        content: "支持颜色、尺寸与礼赠需求沟通，和创作者一起完成专属设计。",
        buttonLabel: "咨询定制",
        enabled: true,
      },
      {
        id: "collection",
        label: "作品陈列",
        title: "正在制作与出售",
        content: "探索工作室近期完成的手作。",
        buttonLabel: "查看全部作品",
        enabled: true,
      },
      {
        id: "footer",
        label: "页脚",
        title: "认真制作，慢慢相遇",
        content: "作品 · 关于我们 · 定制说明 · 配送与退货",
        enabled: true,
      },
    ],
    prestige: [
      {
        id: "header",
        label: "导航栏",
        title: "作品　关于　联系",
        content: "",
        enabled: true,
      },
      {
        id: "hero",
        label: "首屏横幅",
        title: "把日常做成值得收藏的作品",
        content: "从材质、手感到时间痕迹，每件作品都有自己的故事。",
        buttonLabel: "探索作品",
        enabled: true,
      },
      {
        id: "story",
        label: "品牌故事",
        title: "为真实生活而作",
        content: "我们相信手作不是装饰，而是陪伴日常的温度。",
        enabled: true,
      },
      {
        id: "collection",
        label: "精选作品",
        title: "本季精选",
        content: "从店铺已上架作品中挑选给访客。",
        buttonLabel: "浏览全部作品",
        enabled: true,
      },
      {
        id: "newsletter",
        label: "订阅邀请",
        title: "收到新作与创作日记",
        content: "新品发布、限量系列与工作室故事会第一时间送达。",
        buttonLabel: "订阅更新",
        enabled: true,
      },
      {
        id: "footer",
        label: "页脚",
        title: "认真制作，慢慢相遇",
        content: "作品 · 关于我们 · 定制说明 · 配送与退货",
        enabled: true,
      },
    ],
  };
const brandSiteTemplateInfo: Record<
  BrandSiteTemplate,
  { title: string; reference: string; description: string; tags: string[] }
> = {
  dawn: {
    title: "留白集",
    reference: "平台原创主题",
    description: "清爽克制的作品陈列，让商品成为主角。",
    tags: ["简约", "商品优先"],
  },
  craft: {
    title: "原野手记",
    reference: "平台原创主题",
    description: "突出制作过程、工作室故事与定制服务。",
    tags: ["手作故事", "自然感"],
  },
  prestige: {
    title: "幕间",
    reference: "平台原创主题",
    description: "以大图和留白营造有质感的品牌氛围。",
    tags: ["编辑感", "高级感"],
  },
};
const brandSiteTemplatePreviewImages: Record<BrandSiteTemplate, string> = {
  dawn: ceramicCupImage,
  craft: woolTableRunnerImage,
  prestige: moonstoneEarringsImage,
};
const brandSiteAdditionalSections: Record<
  Exclude<
    BrandSiteSectionId,
    | "announcement"
    | "header"
    | "hero"
    | "story"
    | "collection"
    | "columns"
    | "maker"
    | "services"
    | "promise"
    | "newsletter"
    | "footer"
  >,
  BrandSiteSection
> = {
  "image-text": {
    id: "image-text",
    label: "图文介绍",
    title: "用一段故事，介绍你的创作",
    content: "上传一张图片，讲述材料、工艺或品牌理念，让访客更了解你的作品。",
    buttonLabel: "了解更多",
    enabled: true,
    imageUrl: "",
  },
  testimonials: {
    id: "testimonials",
    label: "买家评价",
    title: "来自买家的喜欢",
    content: "每一份真诚的反馈，都是我们继续创作的动力。",
    enabled: true,
  },
  faq: {
    id: "faq",
    label: "常见问题",
    title: "购买前想了解什么？",
    content: "你可以在这里说明制作周期、定制方式、配送和售后问题。",
    enabled: true,
  },
};
const normalizeBrandSiteTemplate = (template: unknown): BrandSiteTemplate => {
  if (template === "studio") return "craft";
  if (template === "editorial") return "prestige";
  if (template === "minimal") return "dawn";
  return template === "craft" || template === "prestige" ? template : "dawn";
};
const createBrandSiteSections = (template: BrandSiteTemplate) =>
  brandSiteTemplateSections[template].map((section) => ({ ...section }));
const ensureBrandSiteSections = (
  sections: BrandSiteSection[] | undefined,
  template: BrandSiteTemplate,
) => {
  const current = sections?.length
    ? sections.map((section) => ({ ...section }))
    : createBrandSiteSections(template);
  if (template === "dawn") {
    const announcement = brandSiteTemplateSections.dawn.find(
      (section) => section.id === "announcement",
    )!;
    const columns = brandSiteTemplateSections.dawn.find(
      (section) => section.id === "columns",
    )!;
    if (!current.some((section) => section.id === "announcement"))
      current.unshift({ ...announcement });
    if (!current.some((section) => section.id === "columns")) {
      const newsletterIndex = current.findIndex(
        (section) => section.id === "newsletter",
      );
      current.splice(
        newsletterIndex < 0 ? current.length : newsletterIndex,
        0,
        { ...columns },
      );
    }
  }
  if (!current.some((section) => section.id === "header")) {
    const header = brandSiteTemplateSections[template].find(
      (section) => section.id === "header",
    )!;
    const announcementIndex = current.findIndex(
      (section) => section.id === "announcement",
    );
    current.splice(announcementIndex < 0 ? 0 : announcementIndex + 1, 0, {
      ...header,
    });
  }
  if (!current.some((section) => section.id === "footer"))
    current.push({
      ...brandSiteTemplateSections[template].find(
        (section) => section.id === "footer",
      )!,
    });
  return current;
};
const defaultBrandSite: BrandSiteConfig = {
  enabled: false,
  template: "dawn",
  siteName: "",
  tagline: "",
  themeColor: "#e66020",
  logoUrl: "",
  domain: "",
  status: "draft",
  sections: createBrandSiteSections("dawn"),
};
type InventoryAdjustment = {
  id: string;
  productId: string;
  productTitle: string;
  skuId?: string;
  type: "set" | "increase" | "decrease" | "bulk_set";
  before: number;
  after: number;
  reason: string;
  createdAt: string;
};
export type Product = {
  id: number;
  code?: string;
  title: string;
  category: Category;
  price: number;
  currency?: "USD";
  oldPrice?: number;
  image: string;
  images?: string[];
  mediaAssetIds?: string[];
  imageAssetIds?: string[];
  video?: string;
  videoAssetId?: string;
  listed?: boolean;
  publishStatus?: "published" | "unlisted";
  reviewStatus?: "pending" | "approved" | "rejected";
  moderationReason?: string;
  seoTags?: string[];
  analyticsShopId?: string;
  catalogId?: string;
  sellerId?: string;
  shopId: number;
  shop: string;
  rating: number;
  reviews: number;
  stock: number;
  weightGrams?: number;
  dimensions?: string;
  lowStockThreshold?: number;
  tags: string[];
  custom: boolean;
  description: string;
  material: string;
  craftsmanship?: string;
  shippingOrigin?: string;
  shippingTemplate?: ShippingTemplate;
  buyerTitle?: string;
  buyerDescription?: string;
  buyerMaterial?: string;
  buyerSeoTags?: string[];
  variants?: ProductVariant[];
  skus?: ProductSku[];
};
type ProductDraft = {
  id: number;
  catalogId?: string;
  title: string;
  price: string;
  currency?: "USD";
  category: Category;
  stock: string;
  weightGrams: string;
  dimensions: string;
  lowStockThreshold?: string;
  description: string;
  material: string;
  craftsmanship: string;
  buyerTitle?: string;
  buyerDescription?: string;
  buyerMaterial?: string;
  buyerSeoTags?: string[];
  images: string[];
  mediaAssetIds?: string[];
  imageAssetIds?: string[];
  video: string;
  videoAssetId?: string;
  seoTags?: string[];
  custom: boolean;
  variants: ProductVariant[];
  skus: ProductSku[];
  updatedAt: string;
};
type CartItem = {
  productId: number;
  catalogId?: string;
  quantity: number;
  note?: string;
  variants?: Record<string, string>;
  title?: string;
  image?: string;
  unitPrice?: number;
};
type BuyerAddress = {
  id: string;
  recipient: string;
  phone: string;
  province: string;
  city: string;
  district: string;
  detail: string;
  postalCode?: string;
  countryCode: string;
  country: string;
  isDefault: boolean;
};
type ShippingZone = {
  id: string;
  name: string;
  countries: string[];
  carrier: string;
  firstFee: number;
  additionalFee: number;
  freeShippingThreshold?: number;
  minDeliveryDays: number;
  maxDeliveryDays: number;
  enabled: boolean;
};
type ShippingTemplate = {
  name: string;
  currency?: "USD";
  zones?: ShippingZone[];
  firstFee: number;
  additionalFee: number;
  freeShippingThreshold?: number;
};
type CheckoutQuote = {
  itemAmount: number;
  shippingAmount: number;
  discountAmount: number;
  amount: number;
  currency?: "USD";
  exchangeRate?: string;
  shops?: {
    shopId: string;
    shop: string;
    itemAmount: number;
    shippingAmount: number;
    discountAmount: number;
    amount: number;
    currency?: "USD";
    shippingRule?: {
      zoneId: string;
      zoneName: string;
      carrier: string;
      minDeliveryDays: number;
      maxDeliveryDays: number;
      destinationCountry: string;
      destinationCountryCode: string;
    };
  }[];
};
type Shipment = {
  carrier: string;
  trackingNo: string;
  trackingPhoneLast4?: string;
  events: { time: string; label: string; detail: string }[];
};
export type ShipmentDraft = {
  carrier: string;
  trackingNo: string;
};

export function shipmentTrackingLink(carrier: string, trackingNo: string) {
  const number = encodeURIComponent(trackingNo.trim());
  const normalizedCarrier = carrier.trim().toLowerCase();
  const official = (url: string, requiresPhoneLast4 = false) => ({
    url,
    official: true,
    requiresPhoneLast4,
  });

  if (normalizedCarrier.includes("dhl"))
    return official(
      `https://www.dhl.com/global-en/home/tracking.html?tracking-id=${number}`,
    );
  if (normalizedCarrier.includes("fedex"))
    return official(`https://www.fedex.com/fedextrack/?trknbr=${number}`);
  if (normalizedCarrier === "ups" || normalizedCarrier.includes("ups "))
    return official(`https://www.ups.com/track?tracknum=${number}`);
  if (normalizedCarrier.includes("usps"))
    return official(
      `https://tools.usps.com/go/TrackConfirmAction?tLabels=${number}`,
    );
  if (normalizedCarrier.includes("aramex"))
    return official(
      `https://www.aramex.com/track/shipments?ShipmentNumber=${number}`,
    );
  if (normalizedCarrier.includes("tnt"))
    return official(
      `https://www.tnt.com/express/en_us/site/shipping-tools/tracking.html?searchType=con&cons=${number}`,
    );
  if (
    normalizedCarrier.includes("顺丰") ||
    normalizedCarrier.includes("sf express")
  )
    return official(
      `https://www.sf-express.com/cn/sc/dynamic_function/waybill/#search/bill-number/${number}`,
      true,
    );
  if (
    normalizedCarrier.includes("japan post") ||
    normalizedCarrier.includes("日本邮便")
  )
    return official(
      `https://trackings.post.japanpost.jp/services/srv/search/?requestNo1=${number}`,
    );
  if (normalizedCarrier.includes("australia post"))
    return official(`https://auspost.com.au/mypost/track/#/details/${number}`);

  return {
    url: `https://www.17track.net/en/track#nums=${number}`,
    official: false,
    requiresPhoneLast4: false,
  };
}
export type PaymentMethod = "alipay" | "card";
type Payment = {
  method: PaymentMethod;
  status: "pending" | "succeeded" | "cancelled" | "failed";
  reference?: string;
  paidAt?: string;
  currency?: "USD";
  exchangeRate?: string;
};
export type Order = {
  id: string;
  orderId?: string;
  shopId?: string;
  buyerUserId?: string;
  items: CartItem[];
  status: OrderStatus;
  createdAt: string;
  amount: number;
  currency?: "USD";
  paymentCurrency?: "USD";
  settlementCurrency?: "USD";
  paymentExchangeRate?: string;
  settlementExchangeRate?: string;
  itemAmount?: number;
  shippingAmount?: number;
  discountAmount?: number;
  shipment?: Shipment;
  payment?: Payment;
  reviewed?: boolean;
};
export type ShopMessage = {
  id: string | number;
  shopId: string | number;
  shop?: string;
  buyerUserId?: string;
  buyer?: string;
  sender: "buyer" | "seller";
  type?: "text" | "image" | "order" | "product";
  content: string;
  attachmentUrl?: string;
  order?: {
    id: string;
    orderNo?: string;
    status?: string;
    amount?: number;
    title?: string;
    image?: string;
  } | null;
  product?: {
    id: string;
    title?: string;
    price?: number;
    image?: string;
  } | null;
  read?: boolean;
  automationKind?: string | null;
  priority?: "normal" | "high" | "urgent";
  priorityReason?: string;
  createdAt: string;
};
type NotificationItem = {
  id: string;
  type: string;
  title: string;
  content: string;
  relatedType?: string;
  relatedId?: string;
  read: boolean;
  createdAt: string;
};
export type AfterSaleRequest = {
  id: string | number;
  orderId: string;
  type: "退款" | "退货退款";
  reason: string;
  status: "待处理" | "待退货" | "待收货" | "已同意" | "已拒绝" | "已退款" | "退款已记账";
  createdAt: string;
  amount?: number;
  currency?: "USD";
  exchangeRate?: string;
  refundStatus?: "recorded" | "succeeded" | "failed" | null;
  sellerResponse?: string;
  evidence?: string[];
  returnAddress?: string;
  returnRecipientName?: string;
  returnRecipientPhone?: string;
  returnShipment?: { carrier: string; trackingNo: string; shippedAt: string };
  timeline?: { time: string; label: string; detail: string }[];
};
export type AfterSaleDraft = {
  type: "refund" | "return_refund";
  amount: number;
  reason: string;
  evidence: string[];
};
export type ReviewDraft = {
  rating: number;
  content: string;
  images: string[];
};
export type ReturnShipmentDraft = {
  carrier: string;
  trackingNo: string;
};
export type ProductReview = {
  id: string | number;
  orderId: string;
  productId: number;
  buyerName?: string;
  rating: number;
  content: string;
  sellerReply?: string;
  createdAt: string;
  images?: string[];
  followup?: string;
};
type Shop = {
  id: number;
  analyticsShopId?: string;
  name: string;
  owner: string;
  location: string;
  since: string;
  banner: string;
  avatar: string;
  description: string;
  followers: number;
  status?: "active" | "paused";
  shippingOrigin?: string;
  shippingTemplate?: ShippingTemplate;
  returnPolicy?: ReturnPolicy;
  coupons?: ShopPromotion[];
  featuredProductIds?: Array<string | number>;
  brandSite?: BrandSiteConfig;
};
type FollowedShop = {
  id: string | number;
  name: string;
};
export type AppData = {
  cart: CartItem[];
  favorites: number[];
  followedShops: FollowedShop[];
  orders: Order[];
  messages: ShopMessage[];
  afterSales: AfterSaleRequest[];
  reviews: ProductReview[];
  products: Product[];
  drafts: ProductDraft[];
  shop: Shop;
  role: "buyer" | "seller";
};
type Account = {
  id: string;
  name: string;
  phone?: string;
  email?: string;
  password: string;
  role: "buyer" | "seller" | "admin";
  phoneVerified?: boolean;
  emailVerified?: boolean;
};
type CommunityComment = {
  id: string;
  nickname: string;
  content: string;
  createdAt: string;
  parentCommentId?: string | null;
  imageUrl?: string | null;
  imageUrls?: string[];
};
type CommunityPost = {
  id: string;
  nickname: string;
  category: string;
  title: string;
  content: string;
  createdAt: string;
  comments: CommunityComment[];
  imageUrl?: string | null;
  imageUrls?: string[];
};
type MarketplaceView =
  | "home"
  | "discover"
  | "product"
  | "shop"
  | "cart"
  | "checkout"
  | "orders"
  | "favorites"
  | "coupons"
  | "following"
  | "messages"
  | "notifications"
  | "profile"
  | "security"
  | "community"
  | "information"
  | "studio";
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
const buyerRestorableViews: MarketplaceView[] = [
  "home",
  "discover",
  "cart",
  "checkout",
  "orders",
  "favorites",
  "coupons",
  "following",
  "messages",
  "notifications",
  "profile",
  "security",
  "information",
];
const sellerRestorableViews: MarketplaceView[] = [
  "home",
  "shop",
  "studio",
  "messages",
  "profile",
  "security",
  "notifications",
  "community",
  "information",
];

const productImages = [
  ceramicCupImage,
  moonstoneEarringsImage,
  woolTableRunnerImage,
  springCardImage,
  ceramicCupImage,
  vintageVaseImage,
];

const bundledCatalogImages: Record<string, string> = {
  "product-demo-cup": ceramicCupImage,
};
const bundledMediaImages: Record<string, string> = {
  "local://ceramic-cup.jpg": ceramicCupImage,
};

const seedProducts: Product[] = [
  {
    id: 1,
    title: "山岚手作陶瓷咖啡杯",
    category: "陶艺",
    price: 168,
    image: productImages[0],
    shopId: 1,
    shop: "陶然物语",
    rating: 4.9,
    reviews: 128,
    stock: 12,
    tags: ["手工拉坯", "日用器"],
    custom: true,
    description:
      "每只杯子由陶艺师手工拉坯、上釉与烧制，杯口自然起伏，保留泥土的温度。",
    material: "高白泥、无铅釉",
  },
  {
    id: 2,
    title: "月光石银饰耳坠",
    category: "首饰",
    price: 238,
    oldPrice: 268,
    image: productImages[1],
    shopId: 2,
    shop: "银盐设计",
    rating: 4.8,
    reviews: 76,
    stock: 8,
    tags: ["原创设计", "925银"],
    custom: true,
    description: "微微摇曳的月光石与手工锻打银片，轻盈但有存在感。",
    material: "天然月光石、925银",
  },
  {
    id: 3,
    title: "植物染羊毛桌旗",
    category: "织物",
    price: 320,
    image: productImages[2],
    shopId: 3,
    shop: "一寸织间",
    rating: 5,
    reviews: 42,
    stock: 5,
    tags: ["植物染", "手工织造"],
    custom: true,
    description: "以茜草和板蓝根染出低饱和色彩，每一条纹理均不重复。",
    material: "羊毛、棉麻",
  },
  {
    id: 4,
    title: "手工丝网印刷春日卡片",
    category: "纸艺",
    price: 48,
    image: productImages[3],
    shopId: 4,
    shop: "纸上花园",
    rating: 4.9,
    reviews: 196,
    stock: 30,
    tags: ["插画", "礼物"],
    custom: false,
    description: "四色丝网印刷，将春日花园收进可以寄出的卡片。",
    material: "350g艺术纸",
  },
  {
    id: 5,
    title: "胡桃木黄铜线香座",
    category: "家居",
    price: 128,
    image: productImages[4],
    shopId: 5,
    shop: "木作慢生活",
    rating: 4.9,
    reviews: 89,
    stock: 15,
    tags: ["木作", "极简家居"],
    custom: true,
    description: "手工打磨胡桃木与黄铜，让日常的一炷香有安静的落点。",
    material: "黑胡桃木、黄铜",
  },
  {
    id: 6,
    title: "昭和风复古玻璃花瓶",
    category: "复古",
    price: 188,
    image: productImages[5],
    shopId: 6,
    shop: "旧日好物所",
    rating: 4.7,
    reviews: 31,
    stock: 2,
    tags: ["复古孤品", "昭和"],
    custom: false,
    description: "来自旧时光的透明玻璃花器，细微使用痕迹是它独有的故事。",
    material: "玻璃",
  },
];

const demoShop: Shop = {
  id: 99,
  name: "留白造物",
  owner: "林知夏",
  location: "杭州",
  since: "2022",
  banner: shopBannerImage,
  avatar: shopAvatarImage,
  description: "收集日常灵感，做一些值得长久使用的小物。",
  followers: 1842,
  status: "active",
  shippingOrigin: "浙江省杭州市西湖区",
  shippingTemplate: {
    name: "标准快递",
    firstFee: 8,
    additionalFee: 2,
    freeShippingThreshold: 199,
  },
  returnPolicy: {
    acceptsReturns: true,
    windowDays: 7,
    recipientName: "林知夏",
    recipientPhone: "13800000000",
    address: "浙江省杭州市西湖区",
    instructions: "商品需保持完好、未使用，并附上订单信息。",
  },
  coupons: [],
  featuredProductIds: [],
};
const initialData: AppData = {
  cart: [],
  favorites: [2],
  followedShops: [],
  orders: [],
  messages: [],
  afterSales: [],
  reviews: [],
  products: seedProducts,
  drafts: [],
  shop: demoShop,
  role: "buyer",
};
// The public discovery taxonomy takes its cue from Etsy's well-established
// browse categories, while staying focused on handmade and vintage goods.
const discoveryCategories = [
  { name: "首饰与配饰", slug: "jewelry-accessories", label: "Jewelry & Accessories", image: productImages[1], caption: "One of a kind", matches: ["首饰"] },
  { name: "服饰与鞋履", slug: "clothing-shoes", label: "Clothing & Shoes", image: productImages[2], caption: "Made to wear", matches: ["布艺缝纫", "刺绣", "皮具"] },
  { name: "家居与生活", slug: "home-living", label: "Home & Living", image: productImages[4], caption: "For everyday living", matches: ["家居", "织物", "木质&木艺", "花艺干花"] },
  { name: "婚礼与派对", slug: "weddings-parties", label: "Weddings & Parties", image: productImages[3], caption: "Celebrate beautifully", matches: ["纸艺", "纸品文创", "花艺干花"] },
  { name: "玩具与娱乐", slug: "toys-entertainment", label: "Toys & Entertainment", image: productImages[5], caption: "Made for play", matches: ["微缩景观"] },
  { name: "艺术与收藏", slug: "art-collectibles", label: "Art & Collectibles", image: productImages[5], caption: "Collect a story", matches: ["绘画肌理", "古风国风", "非遗"] },
  { name: "手作材料与工具", slug: "craft-supplies-tools", label: "Craft Supplies & Tools", image: productImages[0], caption: "For your next idea", matches: ["滴胶&树脂", "黏土&塑形"] },
  { name: "复古好物", slug: "vintage", label: "Vintage", image: productImages[5], caption: "Treasures with history", matches: ["复古"] },
  { name: "箱包与手袋", slug: "bags-purses", label: "Bags & Purses", image: productImages[2], caption: "Carry something special", matches: ["皮具", "布艺缝纫"] },
  { name: "纸品与派对用品", slug: "paper-party-supplies", label: "Paper & Party Supplies", image: productImages[3], caption: "Paper stories", matches: ["纸艺", "纸品文创"] },
  { name: "宠物用品", slug: "pet-supplies", label: "Pet Supplies", image: productImages[2], caption: "Made for companions", matches: ["宠物专属"] },
  { name: "洗护与香氛", slug: "bath-beauty", label: "Bath & Beauty", image: productImages[4], caption: "Small daily rituals", matches: ["皂类", "香薰蜡烛 & 香氛"] },
  { name: "陶艺与陶瓷", slug: "ceramics", label: "Ceramics", image: productImages[0], caption: "Clay & fire", matches: ["陶艺", "陶艺陶瓷", "黏土&塑形"] },
  { name: "织物与编织", slug: "textiles-fiber", label: "Textiles & Fiber Arts", image: productImages[2], caption: "Softly made", matches: ["织物", "编织", "羊毛毡", "刺绣"] },
] as const;

const discoveryCategoryByName = (category: string) =>
  discoveryCategories.find((item) => item.name === category);

const discoveryCategoryFromPathname = (pathname: string) => {
  const match = pathname.match(/^\/categories\/([^/]+)\/?$/);
  return match
    ? discoveryCategories.find((item) => item.slug === match[1])
    : undefined;
};

const isDiscoveryCategoryRoute = (pathname: string) =>
  Boolean(discoveryCategoryFromPathname(pathname));

const categoryMatchesProduct = (category: string, productCategory: string) => {
  const definition = discoveryCategoryByName(category);
  return definition
    ? definition.matches.includes(productCategory as never)
    : category === productCategory;
};

const buyerCategoryLabels: Record<string, string> = {
  陶艺: "Ceramics",
  首饰: "Jewelry",
  织物: "Textiles",
  纸艺: "Paper Goods",
  家居: "Home & Living",
  复古: "Vintage",
  布艺: "Textile Crafts",
  手工编织: "Hand Knitting",
  编织: "Knitting & Crochet",
  绘画肌理: "Textured Art",
  布艺缝纫: "Textile Sewing",
  "黏土&塑形": "Clay & Sculpture",
  "滴胶&树脂": "Resin Crafts",
  "木质&木艺": "Woodworking",
  皮具: "Leather Goods",
  陶艺陶瓷: "Ceramics",
  刺绣: "Embroidery",
  花艺干花: "Floral & Dried Flowers",
  "香薰蜡烛 & 香氛": "Candles & Fragrance",
  古风国风: "Traditional Style",
  纸品文创: "Paper & Stationery",
  宠物专属: "For Pets",
  微缩景观: "Miniature Scenes",
  羊毛毡: "Needle Felting",
  皂类: "Soap Making",
  非遗: "Heritage Crafts",
};

function buyerCategoryLabel(category: Category | "全部") {
  return category === "全部"
    ? "All"
    : discoveryCategoryByName(category)?.label || buyerCategoryLabels[category] || category;
}

type BuyerProductCopy = Pick<Product, "title" | "description" | "material">;

// Seller-authored source content stays unchanged in the catalogue. This lookup
// supplies reviewed English copy only when products are rendered for buyers.
const buyerProductCopies: Record<string, BuyerProductCopy> = {
  "1": {
    title: "Mountain Mist Handmade Ceramic Coffee Cup",
    description:
      "Each cup is wheel-thrown, glazed, and fired by hand. Its gently irregular rim preserves the warmth and character of the clay.",
    material: "High-fired white clay, lead-free glaze",
  },
  "2": {
    title: "Moonstone Sterling Silver Drop Earrings",
    description:
      "Softly luminous moonstones are paired with hand-hammered sterling silver for a light, expressive finish.",
    material: "Natural moonstone, sterling silver",
  },
  "3": {
    title: "Botanical-Dyed Wool Table Runner",
    description:
      "Dyed with madder and indigo for muted, natural color. Every woven pattern is one of a kind.",
    material: "Wool, linen",
  },
  "4": {
    title: "Handmade Screen-Printed Spring Cards",
    description:
      "Four-color screen printing brings a spring garden to a card made to be sent and kept.",
    material: "350 gsm fine art paper",
  },
  "5": {
    title: "Walnut & Brass Incense Holder",
    description:
      "Hand-finished walnut and brass give everyday incense a calm, grounded place to rest.",
    material: "Black walnut, brass",
  },
  "6": {
    title: "Vintage Glass Floral Vase",
    description:
      "A clear glass vase with the gentle signs of time, each mark adding to its individual story.",
    material: "Glass",
  },
  "product-demo-cup": {
    title: "Mountain Mist Handmade Ceramic Coffee Cup",
    description: "Each cup is wheel-thrown, glazed, and fired by hand.",
    material: "High-fired white clay, lead-free glaze",
  },
  "legacy-product-user-1784870106607-1784875739615": {
    title: "Handmade Wool Pencil Holder",
    description: "A soft wool pencil holder made by hand for your desk.",
    material: "Handcrafted wool",
  },
  "legacy-product-user-1784870106607-1784872142245": {
    title: "Handmade Eight-Panel Cap",
    description: "A handmade eight-panel cap designed for everyday wear.",
    material: "Handcrafted textile",
  },
  "legacy-product-user-1784870106607-1784966942733": {
    title: "A7 Liberty Fabric Journal Insert",
    description: "A colorful Liberty fabric journal insert in a compact A7 size.",
    material: "Handcrafted fabric",
  },
  "product-1785854300177": {
    title: "Handmade Pearl Floral Wall Art",
    description: "A decorative floral artwork made with pearls.",
    material: "Pearls and mixed media",
  },
  "product-1785912244719": {
    title: "DIY Crochet Flower Bouquet Kit",
    description: "A cheerful yarn flower kit for making a lasting bouquet at home.",
    material: "Yarn and craft supplies",
  },
  "product-1785915424232": {
    title: "Dried Rose Bodhi Root Bead Bracelet",
    description: "A handmade Bodhi root bead bracelet in muted dried-rose tones.",
    material: "Bodhi root beads",
  },
  "product-local-test-20260812": {
    title: "Local Test Product — Not for Sale",
    description:
      "This item is for local development and testing only. Please do not purchase or publish it.",
    material: "Cotton cord and wood components (test item)",
  },
  "product-json-1-20260812": {
    title: "Harris Tweed Handmade Pencil Case",
    description:
      "Handmade from Harris Tweed wool for tidy everyday storage.",
    material: "Harris Tweed wool",
  },
};

function buyerProductCopy(product: Product): BuyerProductCopy {
  const fallback =
    buyerProductCopies[product.catalogId || product.code || String(product.id)] ||
    product;
  return {
    title: product.buyerTitle?.trim() || fallback.title,
    description: product.buyerDescription?.trim() || fallback.description,
    material: product.buyerMaterial?.trim() || fallback.material,
  };
}

function buyerShopName(name: string) {
  const match = name.trim().match(/^(.+)的手作店$/);
  return match ? `${match[1]}'s Handmade Shop` : name;
}

function buyerShopLocation(location: string) {
  return location.trim() === "杭州" ? "Hangzhou" : location;
}

const buyerProductTerms: Record<string, string> = {
  颜色: "Color",
  款式: "Style",
  棕色笔筒: "Brown pencil holder",
  米色笔筒: "Beige pencil holder",
  蓝色笔筒: "Blue pencil holder",
  黄色笔筒: "Yellow pencil holder",
  彩色: "Multicolor",
  灰色: "Gray",
  蓝色: "Blue",
  向日葵: "Sunflower",
  向日葵2: "Sunflower 2",
  大山: "Mountain",
  海浪: "Ocean wave",
  海滩: "Beach",
  蝴蝶: "Butterfly",
  小雏菊: "Daisy",
  玫瑰: "Rose",
  粉色郁金香: "Pink tulip",
  雏菊2: "Daisy 2",
  黄色郁金香: "Yellow tulip",
  小青柠: "Lime",
  干枯玫瑰: "Dried rose",
  栗子茶: "Chestnut tea",
  白玉菩提: "White jade Bodhi",
  白绿渐变: "White-to-green gradient",
  美人鱼: "Mermaid",
  雪柠美人: "Snow lemon",
  泰晤士河: "Thames",
  西太后: "Westminster",
};

function buyerProductTerm(value: string) {
  return buyerProductTerms[value] || value;
}

const buyerSearchLabels: Record<string, string> = {
  陶: "Ceramic",
  陶瓷: "Ceramics",
  手工制作: "Handmade",
  手工编织: "Hand Knitting",
  手链: "Bracelets",
  收纳袋: "Storage Pouches",
  本地测试: "Local Test",
  勿购买: "Not for Sale",
  珍珠画: "Pearl Art",
  礼物装饰画: "Gift Wall Art",
  笔袋: "Pencil Cases",
  菩提手链: "Bodhi Bracelets",
  高端手链: "Premium Bracelets",
  哈里斯粗花呢: "Harris Tweed",
  "A7手账本内页": "A7 Journal Inserts",
};

const DEFAULT_DISCOVER_RECOMMENDATIONS = ["陶瓷", "陶"];

function buyerSearchLabel(value: string) {
  return (
    buyerSearchLabels[value] ||
    buyerCategoryLabels[value] ||
    buyerProductTerm(value)
  );
}

const buyerOrderStatusLabels: Record<OrderStatus, string> = {
  待付款: "Awaiting payment",
  待发货: "Preparing shipment",
  运输中: "In transit",
  待收货: "Delivered",
  已完成: "Complete",
  已取消: "Cancelled",
};

function buyerOrderStatusLabel(status: string) {
  const labels: Record<string, string> = {
    全部: "All orders",
    待处理: "Under review",
    待退货: "Awaiting return",
    已同意: "Approved",
    已拒绝: "Declined",
    已退款: "Refunded",
    ...buyerOrderStatusLabels,
  };
  return labels[status] || status;
}

function createInitialData(account: Account): AppData {
  return {
    ...initialData,
    role: account.role === "seller" ? "seller" : "buyer",
    shop: {
      ...demoShop,
      owner: account.name,
      name: account.role === "seller" ? account.name : `${account.name}的手作店`,
    },
  };
}

// In production the frontend and API are served from the same origin through
// the reverse proxy. Keep the API base relative by default; an absolute
// VITE_API_BASE can still be supplied for a separately hosted API.
const API_BASE =
  (import.meta as ImportMeta & { env?: { VITE_API_BASE?: string } }).env
    ?.VITE_API_BASE ?? "";

let csrfToken = "";

function isApiRequest(input: RequestInfo | URL): boolean {
  try {
    const target = input instanceof Request ? input.url : input.toString();
    const url = new URL(
      target,
      window.location.origin,
    );
    return url.pathname.startsWith("/api/");
  } catch {
    return false;
  }
}

// Keep the CSRF token out of persistent browser storage. Install the wrapper
// globally so lazy-loaded pages use the same protected client as App.tsx.
const nativeFetch = globalThis.fetch.bind(globalThis);
const csrfFetch: typeof globalThis.fetch = async (input, init) => {
  const method = (init?.method ?? (input instanceof Request ? input.method : "GET")).toUpperCase();
  const needsCsrf = ["POST", "PUT", "PATCH", "DELETE"].includes(method) && isApiRequest(input);
  const headers = new Headers(input instanceof Request ? input.headers : undefined);
  new Headers(init?.headers).forEach((value, name) => headers.set(name, value));
  if (needsCsrf && csrfToken && !headers.has("X-CSRF-Token")) {
    headers.set("X-CSRF-Token", csrfToken);
  }
  // Tests and embedded hosts may replace global fetch after this module has
  // loaded. Use that replacement when present, while avoiding recursion when
  // the global client is our own CSRF wrapper.
  const request =
    globalThis.fetch === csrfFetch
      ? nativeFetch
      : globalThis.fetch.bind(globalThis);
  const response = await request(input, needsCsrf ? { ...init, headers } : init);
  const refreshedToken = response.headers?.get?.("X-CSRF-Token");
  if (refreshedToken) csrfToken = refreshedToken;
  return response;
};
const fetch = csrfFetch;
globalThis.fetch = csrfFetch;

const COS_IMAGE_PROCESSING_HOSTS = new Set([
  "cdn.shouzuohub.com",
]);

/**
 * Keep original media for product pages, but let catalogue cards request a
 * responsive COS-generated WebP thumbnail. Local/demo and non-product media
 * are deliberately left untouched.
 */
export function productListImageUrl(
  source: string | null | undefined,
  width: 160 | 400 | 800,
): string | undefined {
  if (!source) return undefined;
  try {
    const url = new URL(source);
    if (
      !COS_IMAGE_PROCESSING_HOSTS.has(url.hostname) ||
      !url.pathname.startsWith("/products/")
    )
      return source;
    return `${url.origin}${url.pathname}?imageMogr2/thumbnail/${width}x${width}/format/webp`;
  } catch {
    return source;
  }
}

type ProductAnalyticsEvent = {
  type: "product_impression" | "product_click";
  productId: string;
  visitorKey: string;
  placement: string;
  channel: string;
  eventId: string;
};

function analyticsVisitorKey() {
  const fallback = `visitor-${Date.now()}-${Math.random().toString(36).slice(2)}`;
  if (typeof window === "undefined") return fallback;
  const storageKey = "handicrafts_analytics_visitor";
  try {
    const existing = window.localStorage.getItem(storageKey);
    if (existing) return existing;
    const generated =
      typeof crypto !== "undefined" && "randomUUID" in crypto
        ? `visitor-${crypto.randomUUID()}`
        : fallback;
    window.localStorage.setItem(storageKey, generated);
    return generated;
  } catch {
    return fallback;
  }
}

function analyticsEventId() {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto)
    return `event-${crypto.randomUUID()}`;
  return `event-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function publicTrafficChannel() {
  if (typeof window === "undefined") return "direct";
  return (
    new URLSearchParams(window.location.search).get("utm_source") ||
    (document.referrer ? "referral" : "direct")
  );
}

function recordProductAnalytics(events: ProductAnalyticsEvent[]) {
  if (!events.length) return;
  void fetch(`${API_BASE}/api/analytics/events`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ events }),
  }).catch(() => undefined);
}
const IMAGE_PLACEHOLDER =
  "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 320 240'%3E%3Crect width='320' height='240' fill='%23f5f2ed'/%3E%3Ccircle cx='104' cy='86' r='24' fill='%23e2c8b8'/%3E%3Cpath d='M34 191l74-70 48 43 42-35 88 62H34z' fill='%23d6c8ba'/%3E%3Cpath d='M34 191l73-47 47 31 45-39 87 55H34z' fill='%23b9a99a'/%3E%3C/svg%3E";
const DEFAULT_RETURN_POLICY: ReturnPolicy = {
  acceptsReturns: true,
  windowDays: 7,
  recipientName: "",
  recipientPhone: "",
  address: "",
  instructions: "",
};
const websocketUrl = () => {
  const endpoint = new URL(
    API_BASE || window.location.origin,
    window.location.origin,
  );
  endpoint.protocol = endpoint.protocol === "https:" ? "wss:" : "ws:";
  endpoint.pathname = `${endpoint.pathname.replace(/\/$/, "")}/ws`;
  endpoint.search = "";
  return endpoint.toString();
};
const communityWebsocketUrl = (visitorId: string) => {
  const endpoint = new URL(
    API_BASE || window.location.origin,
    window.location.origin,
  );
  endpoint.protocol = endpoint.protocol === "https:" ? "wss:" : "ws:";
  endpoint.pathname = `${endpoint.pathname.replace(/\/$/, "")}/ws/community`;
  endpoint.search = new URLSearchParams({ visitorId }).toString();
  return endpoint.toString();
};

const UPLOAD_IMAGE_MAX_DIMENSION = 1600;
const UPLOAD_IMAGE_MAX_BYTES = 2 * 1024 * 1024;
const MAX_UPLOAD_IMAGE_SIZE = 3 * 1024 * 1024;
const UPLOAD_IMAGE_QUALITY = 0.82;

async function compressImageForUpload(
  file: File,
  maxDimension = UPLOAD_IMAGE_MAX_DIMENSION,
): Promise<string> {
  if (file.size > MAX_UPLOAD_IMAGE_SIZE)
    throw new Error("单张图片不能超过 3MB");
  if (
    !["image/jpeg", "image/png", "image/webp", "image/avif"].includes(file.type)
  ) {
    throw new Error("图片仅支持 JPG、PNG 或 WebP 格式");
  }
  const sourceUrl = URL.createObjectURL(file);
  try {
    const image = await new Promise<HTMLImageElement>((resolve, reject) => {
      const element = new Image();
      element.onload = () => resolve(element);
      element.onerror = () => reject(new Error("图片读取失败"));
      element.src = sourceUrl;
    });
    const scale = Math.min(
      1,
      maxDimension / Math.max(image.naturalWidth, image.naturalHeight),
    );
    let width = Math.max(1, Math.round(image.naturalWidth * scale));
    let height = Math.max(1, Math.round(image.naturalHeight * scale));
    let output = "";
    for (let attempt = 0; attempt < 5; attempt += 1) {
      const canvas = document.createElement("canvas");
      canvas.width = width;
      canvas.height = height;
      const context = canvas.getContext("2d");
      if (!context) throw new Error("图片处理失败，请重试");
      context.drawImage(image, 0, 0, width, height);
      const quality = Math.max(0.52, UPLOAD_IMAGE_QUALITY - attempt * 0.08);
      output = canvas.toDataURL("image/webp", quality);
      const byteLength = Math.max(
        0,
        Math.ceil(((output.length - output.indexOf(",") - 1) * 3) / 4),
      );
      if (byteLength <= UPLOAD_IMAGE_MAX_BYTES || attempt === 4) return output;
      width = Math.max(1, Math.round(width * 0.82));
      height = Math.max(1, Math.round(height * 0.82));
    }
    return output;
  } finally {
    URL.revokeObjectURL(sourceUrl);
  }
}

async function compressImageBlobForUpload(
  file: File,
  maxDimension = UPLOAD_IMAGE_MAX_DIMENSION,
): Promise<Blob> {
  if (file.size > MAX_UPLOAD_IMAGE_SIZE)
    throw new Error("单张图片不能超过 3MB");
  if (
    !["image/jpeg", "image/png", "image/webp", "image/avif"].includes(file.type)
  ) {
    throw new Error("图片仅支持 JPG、PNG 或 WebP 格式");
  }
  const sourceUrl = URL.createObjectURL(file);
  try {
    const image = await new Promise<HTMLImageElement>((resolve, reject) => {
      const element = new Image();
      element.onload = () => resolve(element);
      element.onerror = () => reject(new Error("图片读取失败"));
      element.src = sourceUrl;
    });
    const scale = Math.min(
      1,
      maxDimension / Math.max(image.naturalWidth, image.naturalHeight),
    );
    let width = Math.max(1, Math.round(image.naturalWidth * scale));
    let height = Math.max(1, Math.round(image.naturalHeight * scale));
    for (let attempt = 0; attempt < 5; attempt += 1) {
      const canvas = document.createElement("canvas");
      canvas.width = width;
      canvas.height = height;
      const context = canvas.getContext("2d");
      if (!context) throw new Error("图片处理失败，请重试");
      context.drawImage(image, 0, 0, width, height);
      const quality = Math.max(0.52, UPLOAD_IMAGE_QUALITY - attempt * 0.08);
      const output = await new Promise<Blob>((resolve, reject) =>
        canvas.toBlob(
          (blob) =>
            blob ? resolve(blob) : reject(new Error("图片处理失败，请重试")),
          "image/webp",
          quality,
        ),
      );
      if (output.size <= UPLOAD_IMAGE_MAX_BYTES || attempt === 4) return output;
      width = Math.max(1, Math.round(width * 0.82));
      height = Math.max(1, Math.round(height * 0.82));
    }
    throw new Error("图片处理失败，请重试");
  } finally {
    URL.revokeObjectURL(sourceUrl);
  }
}

function mergeProducts(current: Product[], incoming: Product[]) {
  const productKey = (product: Product) => product.catalogId || String(product.id);
  return [
    ...current.filter(
      (product) =>
        !incoming.some(
          (remote) => productKey(remote) === productKey(product),
        ),
    ),
    ...incoming.map((product) => ({
      ...product,
      image:
        bundledCatalogImages[product.catalogId || ""] ||
        bundledMediaImages[product.image] ||
        product.image,
      images: product.images?.map(
        (image) => bundledMediaImages[image] || image,
      ),
    })),
  ];
}

function usePersistedData(account: Account, isGuest = false) {
  const [data, setData] = useState<AppData>(() => createInitialData(account));
  const [hydrated, setHydrated] = useState(isGuest);

  useEffect(() => {
    let active = true;
    const initial = createInitialData(account);
    setHydrated(isGuest);
    setData(initial);
    if (isGuest)
      return () => {
        active = false;
      };

    if (account.role === "seller") {
      fetch(`${API_BASE}/api/seller/workspace`, { credentials: "include" })
        .then((response) => (response.ok ? response.json() : Promise.reject()))
        .then((workspace: Pick<AppData, "shop" | "products" | "drafts">) => {
          if (!active) return;
          setData({ ...initial, ...workspace, role: "seller" });
        })
        .catch(() => undefined)
        .finally(() => {
          if (active) setHydrated(true);
        });
      return () => {
        active = false;
      };
    }

    const load = async () => {
      try {
        const response = await fetch(`${API_BASE}/api/states/${account.id}`, {
          credentials: "include",
        });
        if (!response.ok) throw new Error("Unable to load application state");
        const payload = (await response.json()) as {
          state: Partial<AppData> | null;
        };
        if (!active) return;
        setData({
          ...initial,
          ...payload.state,
          role: account.role === "seller" ? "seller" : "buyer",
        });
      } catch {
        if (!active) return;
        setData(initial);
      } finally {
        if (active) setHydrated(true);
      }
    };
    void load();
    return () => {
      active = false;
    };
  }, [account.id, account.name, account.phone, account.role, isGuest]);

  useEffect(() => {
    if (isGuest || !hydrated || account.role === "seller") return;
    fetch(`${API_BASE}/api/states/${account.id}`, {
      method: "PUT",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ state: data }),
    }).catch(() => undefined);
  }, [account.id, data, hydrated, isGuest]);

  useEffect(() => {
    if (account.role === "seller") return;
    let active = true;
    fetch(`${API_BASE}/api/catalog/products`)
      .then((response) => (response.ok ? response.json() : Promise.reject()))
      .then((payload: { products: Product[] }) => {
        if (!active || !hydrated) return;
        setData((current) => ({
          ...current,
          products: mergeProducts(current.products, payload.products),
        }));
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, [account.role, hydrated]);
  useEffect(() => {
    if (account.role !== "buyer" || isGuest || !hydrated) return;
    fetch(`${API_BASE}/api/buyer/state`, { credentials: "include" })
      .then((response) => (response.ok ? response.json() : Promise.reject()))
      .then((state: Pick<AppData, "cart" | "favorites" | "followedShops">) => {
        setData((current) => ({ ...current, ...state }));
      })
      .catch(() => undefined);
  }, [account.role, hydrated, isGuest]);
  useEffect(() => {
    if (account.role !== "buyer" || isGuest || !hydrated) return;
    fetch(`${API_BASE}/api/messages/buyer`, { credentials: "include" })
      .then((response) => (response.ok ? response.json() : Promise.reject()))
      .then((payload: { messages: ShopMessage[] }) =>
        setData((current) => ({ ...current, messages: payload.messages })),
      )
      .catch(() => undefined);
  }, [account.role, hydrated, isGuest]);
  useEffect(() => {
    if (account.role !== "seller" || !hydrated || isGuest) return;
    fetch(`${API_BASE}/api/sellers/sync`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        data: {
          shop: data.shop,
          products: data.products.filter((product) => product.shopId === 99),
          drafts: data.drafts,
        },
      }),
    }).catch(() => undefined);
  }, [account.id, account.name, account.role, data, hydrated, isGuest]);
  return [data, setData, hydrated] as const;
}

function money(value: number) {
  return `$${value.toFixed(2)}`;
}

const SHIPPING_COUNTRY_OPTIONS = [
  ["US", "United States"], ["CA", "Canada"], ["GB", "United Kingdom"],
  ["DE", "Germany"], ["FR", "France"], ["IT", "Italy"], ["ES", "Spain"],
  ["NL", "Netherlands"], ["BE", "Belgium"], ["AT", "Austria"], ["IE", "Ireland"],
  ["SE", "Sweden"], ["DK", "Denmark"], ["FI", "Finland"], ["PT", "Portugal"],
  ["PL", "Poland"], ["CZ", "Czechia"], ["LU", "Luxembourg"],
] as const;
const SELLER_SHIPPING_COUNTRY_OPTIONS = [
  ["US", "美国"], ["CA", "加拿大"], ["GB", "英国"], ["DE", "德国"],
  ["FR", "法国"], ["IT", "意大利"], ["ES", "西班牙"], ["NL", "荷兰"],
  ["BE", "比利时"], ["AT", "奥地利"], ["IE", "爱尔兰"], ["SE", "瑞典"],
  ["DK", "丹麦"], ["FI", "芬兰"], ["PT", "葡萄牙"], ["PL", "波兰"],
  ["CZ", "捷克"], ["LU", "卢森堡"],
] as const;

function sellerShippingText(value: string) {
  return ({
    "International shipping": "国际配送", "North America": "北美地区", "Europe": "欧洲地区",
    "Custom region": "自定义区域", "SF International": "顺丰国际",
  } as Record<string, string>)[value] || value;
}

function defaultInternationalShippingTemplate(): ShippingTemplate {
  return {
    name: "国际配送", currency: "USD", firstFee: 12, additionalFee: 3, freeShippingThreshold: 80,
    zones: [
      { id: "north-america", name: "北美地区", countries: ["US", "CA"], carrier: "顺丰国际", firstFee: 12, additionalFee: 3, freeShippingThreshold: 80, minDeliveryDays: 7, maxDeliveryDays: 12, enabled: true },
      { id: "europe", name: "欧洲地区", countries: ["GB", "DE", "FR", "IT", "ES", "NL", "BE", "AT", "IE", "SE", "DK", "FI", "PT", "PL", "CZ", "LU"], carrier: "顺丰国际", firstFee: 15, additionalFee: 4, freeShippingThreshold: 100, minDeliveryDays: 8, maxDeliveryDays: 16, enabled: true },
    ],
  };
}
function swatchColor(value: string) {
  return (
    (
      {
        红色: "#b7332d",
        黄色: "#e8b628",
        蓝色: "#376fae",
        绿色: "#4d8a58",
        黑色: "#242423",
        白色: "#faf9f5",
        米白: "#e7dcc7",
        粉色: "#d98d9d",
        紫色: "#775892",
        棕色: "#80543b",
      } as Record<string, string>
    )[value] || "#d5cec4"
  );
}
function splitVariantValues(values: string) {
  return values
    .split(/[，,]/)
    .map((value) => value.trim())
    .filter(Boolean);
}
const PRODUCT_IMAGE_TYPES = new Set([
  "image/jpeg",
  "image/png",
  "image/webp",
  "image/avif",
]);
const PRODUCT_VIDEO_TYPES = new Set([
  "video/mp4",
  "video/webm",
  "video/quicktime",
]);
const MAX_PRODUCT_IMAGE_SIZE = MAX_UPLOAD_IMAGE_SIZE;
const MAX_PRODUCT_VIDEO_SIZE = 50 * 1024 * 1024;
const SENSITIVE_CONTENT_WORDS = [
  "赌博",
  "博彩",
  "色情",
  "成人",
  "毒品",
  "枪支",
  "仿真枪",
  "管制刀具",
  "盗版",
  "假货",
];

function characterCount(value: string) {
  return Array.from(value.trim()).length;
}

function productTitleCharacterUnits(value: string) {
  return Array.from(value.trim()).reduce(
    (total, character) =>
      total +
      (/[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]/u.test(character)
        ? 5
        : 2),
    0,
  );
}

const DIMENSION_LABELS = ["长", "宽", "高"] as const;

function dimensionValue(value: string) {
  return value.trim().replace(/\s*(?:cm|厘米)$/i, "");
}

function parseProductDimensions(value: string) {
  const labelled = DIMENSION_LABELS.map((label) => {
    const matched = value.match(new RegExp(`${label}\\s*[:：]\\s*([^；;]+)`));
    return dimensionValue(matched?.[1] || "");
  });
  if (labelled.some(Boolean)) return labelled;
  return value
    .split(/\s*[×xX]\s*/)
    .slice(0, 3)
    .map(dimensionValue)
    .concat(["", "", ""])
    .slice(0, 3);
}

function formatProductDimensions(values: string[]) {
  return values
    .map((value, index) => {
      const normalized = dimensionValue(value);
      return normalized ? `${DIMENSION_LABELS[index]}：${normalized} cm` : "";
    })
    .filter(Boolean)
    .join("；");
}

function sensitiveContentWord(value: string) {
  return SENSITIVE_CONTENT_WORDS.find((word) => value.includes(word));
}
function variantCombinationKey(optionValues: Record<string, string>) {
  return Object.entries(optionValues)
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([name, value]) => `${name}:${value}`)
    .join("|");
}
function buildVariantCombinations(variants: ProductVariant[]) {
  return variants.reduce<Record<string, string>[]>(
    (combinations, variant) =>
      combinations.flatMap((combination) =>
        variant.values.map((value) => ({
          ...combination,
          [variant.name]: value,
        })),
      ),
    [{}],
  );
}
function lowStockCount(
  product: Product,
  threshold = product.lowStockThreshold ?? 3,
) {
  if (product.skus?.length)
    return product.skus.filter(
      (sku) =>
        (sku.status ?? "active") === "active" &&
        sku.stock > 0 &&
        sku.stock <= threshold,
    ).length;
  return product.stock > 0 && product.stock <= threshold ? 1 : 0;
}
function StatusPill({
  status,
  className = "",
}: {
  status: OrderStatus;
  className?: string;
}) {
  return (
    <span className={`status status-${status} ${className}`.trim()}>
      {buyerOrderStatusLabel(status)}
    </span>
  );
}
function IconButton({
  icon: Icon,
  label,
  onClick,
  active,
  disabled,
  testId,
}: {
  icon: LucideIcon;
  label: string;
  onClick?: (event: MouseEvent<HTMLButtonElement>) => void;
  active?: boolean;
  disabled?: boolean;
  testId?: string;
}) {
  return (
    <button
      className={`icon-button ${active ? "active" : ""}`}
      title={label}
      aria-label={label}
      data-testid={testId}
      onClick={onClick}
      disabled={disabled}
    >
      <Icon size={20} />
    </button>
  );
}

function NotificationPopover({
  notifications,
  conversationUnread,
  onOpen,
  onOpenMessages,
  onRead,
  onReadAll,
  onViewAll,
}: {
  notifications: NotificationItem[];
  conversationUnread: number;
  onOpen: (item: NotificationItem) => void;
  onOpenMessages: () => void;
  onRead: (ids: string[]) => void;
  onReadAll: () => void;
  onViewAll: () => void;
}) {
  const items = notifications.filter((item) => !["buyer_message", "seller_message"].includes(item.type)).slice(0, 6);
  return (
    <div className="notification-popover" role="dialog" aria-label="Notifications">
      <div className="notification-popover-head">
        <strong>Notifications</strong>
        <button type="button" onClick={onReadAll} disabled={!notifications.some((item) => !item.read)}>
          Mark all read
        </button>
      </div>
      {conversationUnread > 0 && (
        <button type="button" className="notification-popover-message" onClick={onOpenMessages}>
          <span className="notification-popover-dot" />
          <span><b>Messages</b><small>{conversationUnread} unread conversation{conversationUnread === 1 ? "" : "s"}</small></span>
          <ChevronRight size={16} />
        </button>
      )}
      <div className="notification-popover-list">
        {items.map((item) => (
          <button
            type="button"
            key={item.id}
            className={`notification-popover-item${item.read ? "" : " unread"}`}
            onClick={() => {
              if (!item.read) onRead([item.id]);
              onOpen(item);
            }}
          >
            <span className="notification-popover-item-copy"><b>{item.title}</b><small>{item.content}</small></span>
            <span className="notification-popover-item-meta"><small>{item.createdAt}</small><ChevronRight size={15} /></span>
          </button>
        ))}
        {!items.length && !conversationUnread && <p className="notification-popover-empty">No notifications yet.</p>}
      </div>
      <button type="button" className="notification-popover-all" onClick={onViewAll}>View all notifications</button>
    </div>
  );
}

const guestAccount: Account = {
  id: "guest",
  name: "游客",
  password: "",
  role: "buyer",
};

const authRouteMode = () =>
  new URLSearchParams(window.location.search).get("auth") === "register"
    ? "register"
    : "login";
const authRouteRole = () =>
  new URLSearchParams(window.location.search).get("role") === "seller"
    ? "seller"
    : "buyer";
const isAuthRoute = () =>
  ["login", "register"].includes(
    new URLSearchParams(window.location.search).get("auth") || "",
  );
const isPublicBrandSiteRoute = () =>
  new URLSearchParams(window.location.search).get("site") === "1";
const isAdminRoute = (pathname = window.location.pathname) =>
  /^\/admin\/?$/.test(pathname);
const isSellerDashboardRoute = (pathname = window.location.pathname) =>
  /^\/seller\/dashboard\/?$/.test(pathname);
const documentTitleTranslations: Record<string, string> = {
  "加载中": "Loading",
  "登录": "Sign in",
  "注册": "Register",
  "管理后台": "Admin dashboard",
  "运营管理": "Operations",
  "平台治理": "Platform governance",
  "运营工具": "Operations tools",
  "平台财务": "Platform finance",
  "卖家后台": "Seller dashboard",
  "首页": "Home",
  "发现好物": "Discover",
  "作品详情": "Product details",
  "店铺": "Shop",
  "购物车": "Cart",
  "结算": "Checkout",
  "我的订单": "Orders",
  "我的收藏": "Saved items",
  "优惠券": "Coupons",
  "关注店铺": "Following",
  "消息中心": "Messages",
  "买家消息": "Buyer messages",
  "通知": "Notifications",
  "个人中心": "Profile",
  "账号安全": "Account security",
  "创作者社区": "Creator community",
  "帮助中心": "Help center",
  "作品管理": "Products",
  "库存管理": "Inventory",
  "订单管理": "Orders",
  "评价管理": "Reviews",
  "物流管理": "Shipping",
  "售后服务": "After-sales service",
  "成员管理": "Team members",
  "平台支持": "Platform support",
  "营销活动": "Campaigns",
  "经营顾问": "Business advisor",
  "店铺营销": "Marketing",
  "资金中心": "Finance",
  "品牌站": "Brand site",
  "店铺设置": "Shop settings",
  "品牌官网": "Brand site",
};

const setDocumentTitle = (page: string) => {
  document.title = `${documentTitleTranslations[page] || page} | Shouzhou Hub`;
};

const setAuthRoute = (
  visible: boolean,
  mode: "login" | "register" = "login",
  role: "buyer" | "seller" = "buyer",
) => {
  const url = new URL(window.location.href);
  if (visible) {
    url.searchParams.set("auth", mode);
    if (mode === "register" && role === "seller")
      url.searchParams.set("role", "seller");
    else url.searchParams.delete("role");
  } else {
    url.searchParams.delete("auth");
    url.searchParams.delete("role");
  }
  const nextUrl = `${url.pathname}${url.search}${url.hash}`;
  if (
    nextUrl !==
    `${window.location.pathname}${window.location.search}${window.location.hash}`
  )
    window.history.replaceState(null, "", nextUrl);
};

export default function App() {
  const [account, setAccount] = useState<Account | null>(null);
  const [showAuth, setShowAuth] = useState(isAuthRoute);
  const [sessionReady, setSessionReady] = useState(false);
  const [pathname, setPathname] = useState(() => window.location.pathname);
  useEffect(() => {
    const syncPathname = () => setPathname(window.location.pathname);
    window.addEventListener("popstate", syncPathname);
    return () => window.removeEventListener("popstate", syncPathname);
  }, []);
  useEffect(() => {
    if (isPublicBrandSiteRoute()) return setDocumentTitle("品牌官网");
    if (!sessionReady) return setDocumentTitle("加载中");
    if (!account && showAuth)
      return setDocumentTitle(authRouteMode() === "register" ? "注册" : "登录");
    if (isAdminRoute(pathname)) return setDocumentTitle("管理后台");
    if (isSellerDashboardRoute(pathname)) return setDocumentTitle("卖家后台");
  }, [account, pathname, sessionReady, showAuth]);
  useEffect(() => {
    const applyPlaceholder = (image: HTMLImageElement) => {
      if (image.dataset.placeholderApplied) return;
      image.dataset.placeholderApplied = "true";
      image.src = IMAGE_PLACEHOLDER;
    };
    const handleImageError = (event: Event) => {
      if (event.target instanceof HTMLImageElement)
        applyPlaceholder(event.target);
    };
    document.addEventListener("error", handleImageError, true);
    document.querySelectorAll("img").forEach((image) => {
      if (image.complete && image.naturalWidth === 0) applyPlaceholder(image);
    });
    return () => document.removeEventListener("error", handleImageError, true);
  }, []);
  useEffect(() => {
    let active = true;
    const restoreSession = async () => {
      try {
        const response = await fetch(`${API_BASE}/api/auth/session`, {
          credentials: "include",
        });
        const payload = response.ok
          ? ((await response.json()) as { account: Account | null })
          : { account: null };
        if (active) {
          setAccount(payload.account);
          if (payload.account) {
            setShowAuth(false);
            setAuthRoute(false);
          }
        }
      } catch {
        // Guest mode remains available if the local API is unavailable.
      } finally {
        if (active) setSessionReady(true);
      }
    };
    void restoreSession();
    return () => {
      active = false;
    };
  }, []);

  const closeAuth = () => {
    setShowAuth(false);
    setAuthRoute(false);
  };
  const routeAfterAuthentication = (nextAccount: Account) => {
    const url = new URL(window.location.href);
    url.pathname =
      nextAccount.role === "admin"
        ? "/admin/"
        : nextAccount.role === "seller"
          ? "/seller/dashboard/"
          : "/";
    ["view", "product", "brandEditor", "adminSection"].forEach((key) =>
      url.searchParams.delete(key),
    );
    window.history.replaceState(null, "", `${url.pathname}${url.search}${url.hash}`);
    setPathname(url.pathname);
  };
  const openAuth = () => {
    setShowAuth(true);
    setAuthRoute(true);
  };
  const openSellerRegistration = () => {
    setShowAuth(true);
    setAuthRoute(true, "register", "seller");
  };

  const login = async (identifier: string, password: string) => {
    try {
      const response = await fetch(`${API_BASE}/api/auth/login`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ identifier, password }),
      });
      const payload = (await response.json()) as {
        account?: Account;
        error?: string;
      };
      if (!response.ok || !payload.account)
        return payload.error || "Incorrect email, phone number, or password";
      setAccount(payload.account);
      closeAuth();
      routeAfterAuthentication(payload.account);
      return "";
    } catch {
      return "Could not connect to the service. Please try again.";
    }
  };
  const register = async (
    name: string,
    phone: string,
    email: string,
    password: string,
    confirmPassword: string,
    phoneVerificationCode: string,
    role: Account["role"],
  ) => {
    const normalizedEmail = email.trim().toLowerCase();
    if (
      !name.trim() ||
      !password ||
      (role === "seller" ? !phone : !phone && !normalizedEmail)
    )
      return role === "seller"
        ? "Seller registration requires a shop name, phone number, and password"
        : "Enter a display name, password, and at least one sign-in method";
    if (phone && !/^1\d{10}$/.test(phone)) return "Enter a valid 11-digit phone number";
    if (normalizedEmail && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(normalizedEmail))
      return "Enter a valid email address";
    if (password.length < 8) return "Your password must be at least 8 characters";
    if (password !== confirmPassword) return "The passwords do not match";
    try {
      const response = await fetch(`${API_BASE}/api/auth/register`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: name.trim(),
          phone,
          email: normalizedEmail,
          password,
          confirmPassword,
          phoneVerificationCode,
          role,
        }),
      });
      const payload = (await response.json()) as {
        account?: Account;
        error?: string;
      };
      if (!response.ok || !payload.account) return payload.error || "Account could not be created";
      setAccount(payload.account);
      closeAuth();
      routeAfterAuthentication(payload.account);
      return "";
    } catch {
      return "Could not connect to the service. Please try again.";
    }
  };
  const logout = async () => {
    try {
      await fetch(`${API_BASE}/api/auth/logout`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: "{}",
      });
    } finally {
      const url = new URL(window.location.href);
      url.pathname = "/";
      ["view", "tab", "product", "brandEditor", "adminSection"].forEach((key) =>
        url.searchParams.delete(key),
      );
      window.history.replaceState(
        null,
        "",
        `${url.pathname}${url.search}${url.hash}`,
      );
      setPathname(url.pathname);
      setAccount(null);
    }
  };
  const updateAccount = (changes: Partial<Account>) => {
    setAccount((current) => (current ? { ...current, ...changes } : current));
  };

  const protectedRouteDenied =
    (isAdminRoute(pathname) && account?.role !== "admin") ||
    (isSellerDashboardRoute(pathname) && account?.role !== "seller");
  useEffect(() => {
    if (!sessionReady || !protectedRouteDenied) return;
    const url = new URL(window.location.href);
    url.pathname = "/";
    url.searchParams.delete("adminSection");
    url.searchParams.delete("tab");
    window.history.replaceState(null, "", `${url.pathname}${url.search}${url.hash}`);
    setPathname(url.pathname);
  }, [protectedRouteDenied, sessionReady]);

  if (isPublicBrandSiteRoute())
    return (
      <Suspense fallback={<main className="app-loading" aria-busy="true"><span /></main>}>
        <LazyPublicBrandSite
          context={{
            apiBase: API_BASE,
            setDocumentTitle,
            previewDependencies: {
              apiBase: API_BASE,
              normalizeBrandSiteTemplate,
              ensureBrandSiteSections,
              productListImageUrl,
              bundledCatalogImages,
              bundledMediaImages,
              buyerProductCopy,
              money,
            },
          }}
        />
      </Suspense>
    );
  if (!sessionReady)
    return (
      <main
        className="app-loading"
        aria-busy="true"
        aria-label="正在恢复登录状态"
      >
        <span />
      </main>
    );
  if (!account && showAuth)
    return (
      <AuthScreen
        onLogin={login}
        onRegister={register}
        onBack={closeAuth}
        initialMode={authRouteMode()}
        initialRole={authRouteRole()}
      />
    );
  if (protectedRouteDenied)
    return <main className="app-loading" aria-busy="true"><span /></main>;
  return isAdminRoute(pathname) && account?.role === "admin" ? (
    <Suspense fallback={<main className="app-loading" aria-busy="true"><span /></main>}>
      <LazyAdminConsole
        account={account}
        onLogout={logout}
        compressImageForUpload={compressImageForUpload}
        setDocumentTitle={setDocumentTitle}
      />
    </Suspense>
  ) : (
    <Marketplace
      key={account?.id || guestAccount.id}
      account={account || guestAccount}
      isGuest={!account}
      onAuth={openAuth}
      onSellerRegistration={openSellerRegistration}
      onLogout={logout}
      onAccountUpdated={updateAccount}
      onAccountDeleted={() => setAccount(null)}
    />
  );
}

export function AuthScreen({
  onLogin,
  onRegister,
  onBack,
  initialMode = "login",
  initialRole = "buyer",
}: {
  onLogin: (identifier: string, password: string) => Promise<string>;
  onRegister: (
    name: string,
    phone: string,
    email: string,
    password: string,
    confirmPassword: string,
    phoneVerificationCode: string,
    role: Account["role"],
  ) => Promise<string>;
  onBack: () => void;
  initialMode?: "login" | "register";
  initialRole?: "buyer" | "seller";
}) {
  const [mode, setMode] = useState<"login" | "register" | "forgot">(
    initialMode,
  );
  const [name, setName] = useState("");
  const [identifier, setIdentifier] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [phoneVerificationCode, setPhoneVerificationCode] = useState("");
  const [phoneDevelopmentCode, setPhoneDevelopmentCode] = useState("");
  const [phoneCodeSent, setPhoneCodeSent] = useState(false);
  const [sendingPhoneCode, setSendingPhoneCode] = useState(false);
  const [role, setRole] = useState<Account["role"]>(initialRole);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [resetDestination, setResetDestination] = useState("");
  const [resetCode, setResetCode] = useState("");
  const [resetPassword, setResetPassword] = useState("");
  const [resetConfirmPassword, setResetConfirmPassword] = useState("");
  const [resetCodeSent, setResetCodeSent] = useState(false);
  const [resetDevelopmentCode, setResetDevelopmentCode] = useState("");
  const [sendingResetCode, setSendingResetCode] = useState(false);
  const requestPhoneCode = async () => {
    setError("");
    if (!/^1\d{10}$/.test(phone)) {
      setError("请先填写正确的 11 位手机号");
      return;
    }
    setSendingPhoneCode(true);
    try {
      const response = await fetch(
        `${API_BASE}/api/auth/request-verification`,
        {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            destination: phone,
            purpose: "contact_verify",
            registration: true,
          }),
        },
      );
      const payload = (await response.json().catch(() => ({}))) as {
        error?: string;
        developmentCode?: string;
        testingCode?: string;
      };
      if (!response.ok) {
        setError(payload.error || "验证码发送失败");
        return;
      }
      setPhoneCodeSent(true);
      setPhoneDevelopmentCode(
        payload.testingCode || payload.developmentCode || "",
      );
    } catch {
      setError("服务连接失败，请稍后重试");
    } finally {
      setSendingPhoneCode(false);
    }
  };
  const requestResetCode = async () => {
    const destination = resetDestination.trim().toLowerCase();
    if (
      !/^1\d{10}$/.test(destination) &&
      !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(destination)
    ) {
      setError("请输入已绑定的手机号或邮箱");
      return;
    }
    setError("");
    setSendingResetCode(true);
    try {
      const response = await fetch(
        `${API_BASE}/api/auth/request-verification`,
        {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ destination, purpose: "password_reset" }),
        },
      );
      const payload = (await response.json().catch(() => ({}))) as {
        error?: string;
        developmentCode?: string;
      };
      if (!response.ok)
        return setError(payload.error || "验证码发送失败，请稍后重试");
      setResetCodeSent(true);
      setResetDevelopmentCode(payload.developmentCode || "");
    } catch {
      setError("服务连接失败，请稍后重试");
    } finally {
      setSendingResetCode(false);
    }
  };
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (mode === "forgot") {
      const destination = resetDestination.trim().toLowerCase();
      if (
        !resetCodeSent ||
        !/^\d{6}$/.test(resetCode) ||
        resetPassword.length < 8
      ) {
        setError("请填写验证码和至少 8 位的新密码");
        return;
      }
      if (resetPassword !== resetConfirmPassword) {
        setError("两次输入的新密码不一致");
        return;
      }
      setSubmitting(true);
      try {
        const response = await fetch(`${API_BASE}/api/auth/reset-password`, {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            destination,
            code: resetCode,
            password: resetPassword,
          }),
        });
        const payload = (await response.json().catch(() => ({}))) as {
          error?: string;
        };
        if (!response.ok) return setError(payload.error || "密码重置失败");
        setMode("login");
        setIdentifier(destination);
        setPassword("");
        setResetCode("");
        setResetPassword("");
        setResetConfirmPassword("");
        setResetDevelopmentCode("");
        setResetCodeSent(false);
        setError("密码已重置，请使用新密码登录");
      } catch {
        setError("服务连接失败，请稍后重试");
      } finally {
        setSubmitting(false);
      }
      return;
    }
    if (mode === "register" && password !== confirmPassword) {
      setError("两次输入的密码不一致");
      return;
    }
    setSubmitting(true);
    const message = await (mode === "login"
      ? onLogin(identifier.trim(), password)
      : onRegister(
          name,
          phone,
          email,
          password,
          confirmPassword,
          phoneVerificationCode,
          role,
        ));
    setError(message);
    setSubmitting(false);
  };
  return (
    <main className="auth-page">
      <section className="auth-art">
        <div className="auth-brand">
          Shouzuo <span>Hub</span>
        </div>
        <div>
          <p>HANDMADE, ORIGINAL, YOURS</p>
          <h1>Give thoughtfully made things the attention they deserve.</h1>
          <span>Discover independent makers, or start sharing your own work.</span>
        </div>
      </section>
      <section className="auth-panel">
        <div className="auth-card">
          <div className="auth-tabs">
            <button
              data-testid="auth-login-tab"
              className={mode === "login" ? "active" : ""}
              onClick={() => {
                setMode("login");
                setError("");
              }}
            >
              Sign in
            </button>
            <button
              data-testid="auth-register-tab"
              className={mode === "register" ? "active" : ""}
              onClick={() => {
                setMode("register");
                setError("");
              }}
            >
              Sign up
            </button>
          </div>
          <h2>
            {mode === "login"
              ? "Welcome back"
              : mode === "forgot"
                ? "Reset your password"
                : "Create your account"}
          </h2>
          <p>
            {mode === "login"
              ? "Sign in to continue your handmade journey."
              : mode === "forgot"
                ? "Verify your phone number or email, then choose a new password."
                : "Create an account to browse, shop, or open your own store."}
          </p>
          <form data-testid="auth-form" onSubmit={submit}>
            {mode === "forgot" ? (
              <>
                <label>
                  Linked phone number or email
                  <input
                    data-testid="reset-destination"
                    value={resetDestination}
                    onChange={(event) => {
                      setResetDestination(event.target.value);
                      setResetCode("");
                      setResetCodeSent(false);
                      setResetDevelopmentCode("");
                    }}
                    placeholder="Enter your phone number or email"
                    autoComplete="username"
                  />
                </label>
                <label>
                  Verification code
                  <div className="auth-code-row">
                    <input
                      data-testid="reset-code"
                      value={resetCode}
                      onChange={(event) =>
                        setResetCode(
                          event.target.value.replace(/\D/g, "").slice(0, 6),
                        )
                      }
                      placeholder="Enter the 6-digit code"
                      inputMode="numeric"
                      maxLength={6}
                      autoComplete="one-time-code"
                    />
                    <button
                      className="secondary"
                      type="button"
                      onClick={() => void requestResetCode()}
                      disabled={sendingResetCode}
                    >
                      {sendingResetCode
                        ? "Sending…"
                        : resetCodeSent
                          ? "Resend"
                          : "Send code"}
                    </button>
                  </div>
                </label>
                {resetDevelopmentCode && (
                  <small className="auth-hint">
                    Development code: {resetDevelopmentCode}
                  </small>
                )}
                <label>
                  New password
                  <input
                    data-testid="reset-password"
                    value={resetPassword}
                    onChange={(event) => setResetPassword(event.target.value)}
                    placeholder="At least 8 characters"
                    type="password"
                    minLength={8}
                    autoComplete="new-password"
                  />
                </label>
                <label>
                  Confirm new password
                  <input
                    data-testid="reset-confirm-password"
                    value={resetConfirmPassword}
                    onChange={(event) =>
                      setResetConfirmPassword(event.target.value)
                    }
                    placeholder="Enter your new password again"
                    type="password"
                    minLength={8}
                    autoComplete="new-password"
                  />
                </label>
                {error && (
                  <div className="auth-error" role="alert">
                    {error}
                  </div>
                )}
                <button
                  data-testid="reset-submit"
                  className="primary full"
                  type="submit"
                  disabled={submitting}
                >
                  {submitting ? "Resetting…" : "Reset password"}
                </button>
                <button
                  className="auth-text-link"
                  type="button"
                  onClick={() => {
                    setMode("login");
                    setError("");
                  }}
                >
                  Back to sign in
                </button>
              </>
            ) : (
              <>
                {mode === "register" && (
                  <label>
                    {role === "seller" ? "Shop name" : "Display name"}
                    <input
                      data-testid="auth-name"
                      value={name}
                      onChange={(event) => setName(event.target.value)}
                      placeholder={
                        role === "seller"
                          ? "What is your shop called?"
                          : "How should we address you?"
                      }
                      autoComplete={role === "seller" ? "organization" : "name"}
                    />
                  </label>
                )}
                {mode === "login" ? (
                  <label>
                    Phone number or email
                    <input
                      data-testid="auth-identifier"
                      value={identifier}
                      onChange={(event) => setIdentifier(event.target.value)}
                      placeholder="Enter your phone number or email"
                      autoComplete="username"
                    />
                  </label>
                ) : (
                  <>
                    <label>
                      Phone number{role === "seller" ? "" : " (optional)"}
                      <input
                        data-testid="auth-phone"
                        value={phone}
                        onChange={(event) =>
                          (() => {
                            setPhone(
                              event.target.value
                                .replace(/\D/g, "")
                                .slice(0, 11),
                            );
                            setPhoneVerificationCode("");
                            setPhoneCodeSent(false);
                            setPhoneDevelopmentCode("");
                          })()
                        }
                        placeholder="Phone number"
                        inputMode="numeric"
                        autoComplete="tel"
                        required={role === "seller"}
                      />
                    </label>
                    {role === "seller" && (
                      <div className="seller-phone-verification">
                        <div className="seller-phone-code-row">
                          <input
                            data-testid="auth-phone-code"
                            value={phoneVerificationCode}
                            onChange={(event) =>
                              setPhoneVerificationCode(
                                event.target.value
                                  .replace(/\D/g, "")
                                  .slice(0, 6),
                              )
                            }
                            placeholder="Enter the 6-digit code"
                            inputMode="numeric"
                            maxLength={6}
                            required
                          />
                          <button
                            data-testid="auth-phone-code-request"
                            className="secondary"
                            type="button"
                            onClick={() => void requestPhoneCode()}
                            disabled={sendingPhoneCode}
                          >
                            {phoneCodeSent ? "Resend" : "Send code"}
                          </button>
                        </div>
                        {phoneDevelopmentCode && (
                          <div className="testing-verification-code">
                            <span>Test verification code</span>
                            <strong>{phoneDevelopmentCode}</strong>
                            <small>
                              Enter this above. The code is valid for 2 minutes.
                            </small>
                          </div>
                        )}
                      </div>
                    )}
                    <label>
                      Email (optional)
                      <input
                        data-testid="auth-email"
                        value={email}
                        onChange={(event) => setEmail(event.target.value)}
                        placeholder="name@example.com"
                        inputMode="email"
                        autoComplete="email"
                      />
                    </label>
                    <small className="auth-hint">
                      {role === "seller"
                        ? "We’ll send a 6-digit verification code to confirm your phone number."
                        : "Enter at least a phone number or email. Either can be used to sign in."}
                    </small>
                  </>
                )}
                <label>
                  Password
                  <input
                    data-testid="auth-password"
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    placeholder={mode === "register" ? "At least 8 characters" : "Enter your password"}
                    type="password"
                    autoComplete={
                      mode === "login" ? "current-password" : "new-password"
                    }
                  />
                </label>
                {mode === "register" && (
                  <label>
                    Confirm password
                    <input
                      data-testid="auth-confirm-password"
                      value={confirmPassword}
                      onChange={(event) =>
                        setConfirmPassword(event.target.value)
                      }
                      placeholder="Enter your password again"
                      type="password"
                      autoComplete="new-password"
                    />
                  </label>
                )}
                {mode === "register" && (
                  <div className="role-options">
                    <span>Register as</span>
                    <label className={role === "buyer" ? "selected" : ""}>
                      <input
                        type="radio"
                        checked={role === "buyer"}
                        onChange={() => setRole("buyer")}
                      />
                      Buyer<small>Discover and shop handmade</small>
                    </label>
                    <label className={role === "seller" ? "selected" : ""}>
                      <input
                        type="radio"
                        checked={role === "seller"}
                        onChange={() => setRole("seller")}
                      />
                      Seller<small>Manage products and orders</small>
                    </label>
                  </div>
                )}
                {error && (
                  <div className="auth-error" role="alert">
                    <span>{error}</span>
                    {mode === "register" && error.includes("已注册") && (
                      <button
                        type="button"
                        onClick={() => {
                          setMode("login");
                          setIdentifier(phone || email);
                          setError("");
                        }}
                      >
                        Sign in
                      </button>
                    )}
                  </div>
                )}
                <button
                  data-testid="auth-submit"
                  className="primary full"
                  type="submit"
                  disabled={submitting}
                >
                  {mode === "login"
                    ? "Sign in"
                    : role === "seller"
                      ? "Create seller account"
                      : "Sign up"}
                </button>
              </>
            )}
          </form>
          <div className="auth-actions-row">
            {mode === "login" && (
              <button
                data-testid="auth-forgot-password"
                className="auth-text-link"
                type="button"
                onClick={() => {
                  setMode("forgot");
                  setError("");
                }}
              >
                Forgot password?
              </button>
            )}
            <button type="button" className="auth-back" onClick={onBack}>
              Back to home
            </button>
          </div>
        </div>
      </section>
    </main>
  );
}

function Marketplace({
  account,
  onLogout,
  onAccountUpdated,
  onAccountDeleted,
  isGuest = false,
  onAuth,
  onSellerRegistration,
}: {
  account: Account;
  onLogout: () => void;
  onAccountUpdated: (changes: Partial<Account>) => void;
  onAccountDeleted: () => void;
  isGuest?: boolean;
  onAuth: () => void;
  onSellerRegistration: () => void;
}) {
  const [data, setData, hydrated] = usePersistedData(account, isGuest);
  const initialProductId = Number(
    new URLSearchParams(window.location.search).get("product"),
  );
  const initialView = new URLSearchParams(window.location.search).get("view");
  const shopPreview =
    new URLSearchParams(window.location.search).get("shopPreview") === "1";
  const initialDiscoveryCategory = discoveryCategoryFromPathname(
    window.location.pathname,
  );
  const standaloneRouteView: MarketplaceView | null =
    /^\/community\/?$/.test(window.location.pathname)
      ? "community"
      : /^\/discover\/?$/.test(window.location.pathname)
        ? "discover"
        : /^\/seller\/dashboard\/?$/.test(window.location.pathname)
          ? "studio"
          : /^\/shop\/?$/.test(window.location.pathname)
            ? "shop"
            : null;
  const standaloneBrandEditor =
    new URLSearchParams(window.location.search).get("brandEditor") === "1";
  const canRestoreInitialView =
    account.role === "buyer"
      ? buyerRestorableViews.includes(initialView as MarketplaceView)
      : sellerRestorableViews.includes(initialView as MarketplaceView);
  const [view, setView] = useState<MarketplaceView>(() =>
    Number.isInteger(initialProductId) && initialProductId > 0
      ? "product"
      : standaloneRouteView
        ? standaloneRouteView
        : initialDiscoveryCategory
        ? "discover"
      : canRestoreInitialView
        ? (initialView as MarketplaceView)
        : "home",
  );
  // Only the seller workspace is localized for merchant operations. All
  // customer-facing pages remain English, regardless of the signed-in role.
  const englishPublicHeader = true;
  const [selectedId, setSelectedId] = useState(
    Number.isInteger(initialProductId) && initialProductId > 0
      ? initialProductId
      : 1,
  );
  const [query, setQuery] = useState("");
  const [searchOpen, setSearchOpen] = useState(false);
  const searchRef = useRef<HTMLDivElement>(null);
  const [searchSort, setSearchSort] = useState<
    "relevance" | "latest" | "price_asc" | "price_desc" | "sales"
  >("relevance");
  const [searchResults, setSearchResults] = useState<Product[] | null>(null);
  const [personalizedProducts, setPersonalizedProducts] = useState<Product[]>(
    [],
  );
  const [searchMeta, setSearchMeta] = useState<{
    originalQuery: string;
    corrected?: string | null;
    recommendations: string[];
    zeroResult?: { message: string; productId?: string | null } | null;
  }>({ originalQuery: "", recommendations: [] });
  const [searchSuggestions, setSearchSuggestions] = useState<
    {
      value: string;
      type: "history" | "product" | "tag" | "recommendation" | "trending";
      hint: string;
    }[]
  >([]);
  const [category, setCategory] = useState<Category | "全部">(
    initialDiscoveryCategory?.name || "全部",
  );
  const [footerPage, setFooterPage] = useState<FooterPage>("about");
  const [notice, setNotice] = useState("");
  const [shippingId, setShippingId] = useState("");
  const [shippingModalOpen, setShippingModalOpen] = useState(false);
  const [sharedOrders, setSharedOrders] = useState<Order[]>([]);
  const [sharedAfterSales, setSharedAfterSales] = useState<AfterSaleRequest[]>(
    [],
  );
  const [sharedReviews, setSharedReviews] = useState<ProductReview[]>([]);
  const [notificationUnread, setNotificationUnread] = useState(0);
  const [conversationUnread, setConversationUnread] = useState(0);
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [notificationMenuOpen, setNotificationMenuOpen] = useState(false);
  const [addresses, setAddresses] = useState<BuyerAddress[]>([]);
  const [coupons, setCoupons] = useState<
    {
      id: string;
      name: string;
      threshold: number;
      discount: number;
      remaining: number;
      claimed: number;
      used: number;
      available: boolean;
      endsAt?: string;
    }[]
  >([]);
  const [claimableCoupons, setClaimableCoupons] = useState<
    {
      id: string;
      name: string;
      threshold: number;
      discount: number;
      claimLimit: number;
    }[]
  >([]);
  const [visitorKey] = useState(() =>
    account.id === guestAccount.id
      ? analyticsVisitorKey()
      : account.id,
  );
  const [trafficChannel] = useState(
    () =>
      new URLSearchParams(window.location.search).get("utm_source") ||
      (document.referrer ? "referral" : "direct"),
  );
  const refreshCoupons = async () => {
    const response = await fetch(`${API_BASE}/api/buyer/coupons`, {
      credentials: "include",
    });
    if (response.ok) {
      const payload = (await response.json()) as {
        coupons: typeof coupons;
        claimable: typeof claimableCoupons;
      };
      setCoupons(payload.coupons);
      setClaimableCoupons(payload.claimable);
    }
  };
  const cartCount = data.cart.reduce((sum, item) => sum + item.quantity, 0);
  const unifiedUnread = notificationUnread + conversationUnread;
  useEffect(() => {
    if (isGuest) return;
    const load = () =>
      fetch(`${API_BASE}/api/notifications`, { credentials: "include" })
        .then((response) => (response.ok ? response.json() : null))
        .then(
          (
            payload: {
              unread: number;
              notifications: NotificationItem[];
            } | null,
          ) => {
            setNotificationUnread(payload?.unread || 0);
            setNotifications(payload?.notifications || []);
          },
        )
        .catch(() => undefined);
    void load();
    const timer = window.setInterval(load, 30000);
    return () => window.clearInterval(timer);
  }, [account.id, isGuest]);
  useEffect(() => {
    if (isGuest) return;
    const endpoint =
      account.role === "seller"
        ? "/api/messages/seller"
        : "/api/messages/buyer";
    const load = () =>
      fetch(`${API_BASE}${endpoint}`, { credentials: "include" })
        .then((response) => (response.ok ? response.json() : null))
        .then((payload: { conversations?: { unread: number }[] } | null) =>
          setConversationUnread(
            (payload?.conversations || []).reduce(
              (total, item) => total + item.unread,
              0,
            ),
          ),
        )
        .catch(() => undefined);
    void load();
    const timer = window.setInterval(load, 30000);
    return () => window.clearInterval(timer);
  }, [account.id, account.role, isGuest]);
  const marketplaceUrl = (
    nextView: MarketplaceView,
    nextProductId = selectedId,
    nextCategory = category,
  ) => {
    const url = new URL(window.location.href);
    const categoryDefinition = discoveryCategoryByName(nextCategory);
    if (nextView === "product") {
      url.pathname = "/";
      url.searchParams.set("product", String(nextProductId));
      url.searchParams.delete("view");
    } else if (nextView === "discover" && categoryDefinition) {
      url.pathname = `/categories/${categoryDefinition.slug}`;
      url.searchParams.delete("product");
      url.searchParams.delete("view");
    } else if (
      ["home", "discover", "studio", "shop", "community"].includes(nextView)
    ) {
      const paths: Partial<Record<MarketplaceView, string>> = {
        home: "/",
        discover: "/discover/",
        studio: "/seller/dashboard/",
        shop: "/shop/",
        community: "/community/",
      };
      url.pathname = paths[nextView] || "/";
      url.searchParams.delete("product");
      url.searchParams.delete("view");
    } else {
      url.pathname = "/";
      url.searchParams.delete("product");
      url.searchParams.set("view", nextView);
    }
    return `${url.pathname}${url.search}${url.hash}`;
  };
  useEffect(() => {
    const nextUrl = marketplaceUrl(view, selectedId, category);
    if (
      nextUrl !==
      `${window.location.pathname}${window.location.search}${window.location.hash}`
    )
      window.history.replaceState(
        { marketplace: { view, productId: selectedId, category } },
        "",
        nextUrl,
      );
  }, [view, selectedId, category]);
  useEffect(() => {
    const syncFromLocation = () => {
      const url = new URL(window.location.href);
      const params = url.searchParams;
      const productId = Number(params.get("product"));
      const categoryDefinition = discoveryCategoryFromPathname(url.pathname);
      const routeView: MarketplaceView | null = /^\/community\/?$/.test(
        url.pathname,
      )
        ? "community"
        : /^\/discover\/?$/.test(url.pathname)
          ? "discover"
          : /^\/seller\/dashboard\/?$/.test(url.pathname)
            ? "studio"
            : /^\/shop\/?$/.test(url.pathname)
              ? "shop"
              : null;
      const requestedView = params.get("view") as MarketplaceView | null;
      const restorableViews =
        account.role === "buyer" ? buyerRestorableViews : sellerRestorableViews;
      const nextView =
        Number.isInteger(productId) && productId > 0
          ? "product"
          : categoryDefinition
            ? "discover"
            : routeView ||
              (requestedView && restorableViews.includes(requestedView)
                ? requestedView
                : "home");
      const state = window.history.state as {
        marketplace?: { returnView?: MarketplaceView };
      } | null;
      if (Number.isInteger(productId) && productId > 0) setSelectedId(productId);
      setCategory(categoryDefinition?.name || "全部");
      setView(nextView);
      window.scrollTo({ top: 0, behavior: "smooth" });
    };
    window.addEventListener("popstate", syncFromLocation);
    return () => window.removeEventListener("popstate", syncFromLocation);
  }, [account.role]);
  useEffect(() => {
    if (view !== "discover") return;
    const controller = new AbortController();
    const params = new URLSearchParams({
      q: query,
      // Broad public categories map several maker categories, so filtering is
      // completed in the client after the catalogue response is received.
      category:
        category === "全部" || discoveryCategoryByName(category)
          ? ""
          : category,
      sort: searchSort,
    });
    fetch(`${API_BASE}/api/search?${params.toString()}`, {
      credentials: "include",
      signal: controller.signal,
    })
      .then((response) => (response.ok ? response.json() : Promise.reject()))
      .then(
        (payload: {
          products: Product[];
          originalQuery: string;
          corrected?: string | null;
          recommendations?: string[];
          personalizedProducts?: Product[];
          zeroResult?: { message: string; productId?: string | null } | null;
        }) => {
          setSearchResults(payload.products);
          setPersonalizedProducts(payload.personalizedProducts || []);
          setSearchMeta({
            originalQuery: payload.originalQuery,
            corrected: payload.corrected,
            recommendations: payload.recommendations || [],
            zeroResult: payload.zeroResult,
          });
        },
      )
      .catch(() => {
        if (!controller.signal.aborted) {
          setSearchResults(null);
          setPersonalizedProducts([]);
          setSearchMeta({ originalQuery: "", recommendations: [] });
        }
      });
    return () => controller.abort();
  }, [view, query, category, searchSort]);
  useEffect(() => {
    if (account.role !== "buyer") return;
    if (!query.trim()) {
      setSearchSuggestions([]);
      return;
    }
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      fetch(
        `${API_BASE}/api/search/suggestions?q=${encodeURIComponent(query)}`,
        { credentials: "include", signal: controller.signal },
      )
        .then((response) => (response.ok ? response.json() : Promise.reject()))
        .then((payload: { suggestions?: typeof searchSuggestions }) =>
          setSearchSuggestions(payload.suggestions || []),
        )
        .catch(() => {
          if (!controller.signal.aborted) setSearchSuggestions([]);
        });
    }, 140);
    return () => {
      controller.abort();
      window.clearTimeout(timer);
    };
  }, [account.role, query]);
  useEffect(() => {
    const closeWhenClickingOutside = (event: PointerEvent) => {
      if (
        searchRef.current &&
        !searchRef.current.contains(event.target as Node)
      )
        setSearchOpen(false);
    };
    document.addEventListener("pointerdown", closeWhenClickingOutside);
    return () =>
      document.removeEventListener("pointerdown", closeWhenClickingOutside);
  }, []);
  const show = (
    next: typeof view,
    options: {
      productId?: number;
      category?: Category | "全部";
      returnView?: MarketplaceView;
    } = {},
  ) => {
    const buyerOnly = [
      "cart",
      "checkout",
      "orders",
      "favorites",
      "coupons",
      "following",
    ];
    const sellerOnly = ["shop", "studio", "community"];
    const allowed =
      account.role === "buyer"
        ? !sellerOnly.includes(next)
        : !buyerOnly.includes(next);
    const target = allowed ? next : account.role === "buyer" ? "home" : "studio";
    const nextProductId = options.productId ?? selectedId;
    const nextCategory = options.category ?? category;
    const nextUrl = marketplaceUrl(target, nextProductId, nextCategory);
    if (
      nextUrl !==
      `${window.location.pathname}${window.location.search}${window.location.hash}`
    )
      window.history.pushState(
        {
          marketplace: {
            view: target,
            productId: target === "product" ? nextProductId : undefined,
            category: nextCategory,
            returnView: options.returnView,
          },
        },
        "",
        nextUrl,
      );
    if (options.productId !== undefined) setSelectedId(options.productId);
    if (options.category !== undefined) setCategory(options.category);
    setView(target);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };
  const markNotificationsRead = (ids: string[]) => {
    if (!ids.length) return;
    void fetch(`${API_BASE}/api/notifications/read`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ids }),
    });
    setNotifications((items) =>
      items.map((item) => (ids.includes(item.id) ? { ...item, read: true } : item)),
    );
    setNotificationUnread((value) => Math.max(0, value - ids.length));
  };
  const openNotification = (item: NotificationItem) => {
    setNotificationMenuOpen(false);
    if (["buyer_message", "seller_message"].includes(item.type)) return show("messages");
    if (item.relatedType === "product") {
      const product = data.products.find((value) => value.catalogId === item.relatedId);
      if (product) return openProductInNewTab(product.id);
    }
    if (item.relatedType === "shop") return show(account.role === "seller" ? "studio" : "messages");
    show(account.role === "seller" ? "studio" : "orders");
  };
  const markAllNotificationsRead = () => {
    const unreadIds = notifications.filter((item) => !item.read).map((item) => item.id);
    if (!unreadIds.length) return;
    markNotificationsRead(unreadIds);
  };
  const toast = (message: string) => {
    setNotice(message);
    window.setTimeout(() => setNotice(""), 2200);
  };
  const refreshSharedOrders = async () => {
    if (isGuest) return;
    const endpoint = account.role === "seller" ? "seller" : "buyer";
    const response = await fetch(`${API_BASE}/api/orders/${endpoint}`, {
      credentials: "include",
    });
    if (!response.ok) throw new Error("Orders could not be loaded");
    const payload = (await response.json()) as { orders: Order[] };
    setSharedOrders(payload.orders);
    const afterSalesResponse = await fetch(
      `${API_BASE}/api/after-sales/${endpoint}`,
      {
        credentials: "include",
      },
    );
    if (afterSalesResponse.ok) {
      const afterSalesPayload = (await afterSalesResponse.json()) as {
        afterSales: AfterSaleRequest[];
      };
      setSharedAfterSales(afterSalesPayload.afterSales);
    }
    const reviewsResponse = await fetch(`${API_BASE}/api/reviews/${endpoint}`, {
      credentials: "include",
    });
    if (reviewsResponse.ok) {
      const reviewsPayload = (await reviewsResponse.json()) as {
        reviews: ProductReview[];
      };
      setSharedReviews(reviewsPayload.reviews);
    }
  };
  const refreshAddresses = async () => {
    if (isGuest || account.role !== "buyer") return;
    const response = await fetch(`${API_BASE}/api/addresses`, {
      credentials: "include",
    });
    if (!response.ok) throw new Error("Addresses could not be loaded");
    const payload = (await response.json()) as { addresses: BuyerAddress[] };
    setAddresses(payload.addresses);
  };
  useEffect(() => {
    if (isGuest) {
      setSharedOrders([]);
      setSharedAfterSales([]);
      setSharedReviews([]);
      return;
    }
    void refreshSharedOrders().catch(() => setSharedOrders([]));
    void refreshAddresses().catch(() => setAddresses([]));
  }, [account.id, account.role, isGuest]);
  const checkoutItems = () =>
    data.cart.map((item) => {
      const product = data.products.find(
        (value) => value.id === item.productId,
      );
      return { ...item, catalogId: product?.catalogId };
    });
  const quoteCheckout = async (addressId: string) => {
    const response = await fetch(`${API_BASE}/api/checkout/quote`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        items: checkoutItems(),
        addressId,
        channel: trafficChannel,
      }),
    });
    const payload = (await response.json()) as {
      quote?: CheckoutQuote;
      error?: string;
    };
    if (!response.ok) throw new Error(payload.error || "Checkout quote could not be loaded");
    return payload.quote!;
  };
  const createSharedOrders = async (
    addressId: string,
    paymentMethod: PaymentMethod,
  ) => {
    const items = checkoutItems();
    if (items.some((item) => !item.catalogId)) {
      toast("Some items are still syncing and cannot be checked out yet");
      return null;
    }
    const response = await fetch(`${API_BASE}/api/orders`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        items,
        addressId,
        paymentMethod,
        channel: trafficChannel,
      }),
    });
    const payload = (await response.json()) as {
      orders?: Order[];
      error?: string;
    };
    if (!response.ok) {
      toast(payload.error || "Order could not be created");
      return null;
    }
    setData((current) => ({ ...current, cart: [] }));
    const createdOrders = payload.orders || [];
    setSharedOrders((current) => [...createdOrders, ...current]);
    const catalogResponse = await fetch(`${API_BASE}/api/catalog/products`);
    if (catalogResponse.ok) {
      const catalogPayload = (await catalogResponse.json()) as {
        products: Product[];
      };
      setData((current) => ({
        ...current,
        products: mergeProducts(current.products, catalogPayload.products),
      }));
    }
    return createdOrders;
  };
  const paySharedOrder = async (id: string, paymentMethod: PaymentMethod) => {
    const response = await fetch(`${API_BASE}/api/orders/${id}/pay`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ paymentMethod }),
    });
    const payload = (await response.json()) as {
      payment?: { token: string };
      error?: string;
    };
    if (!response.ok) {
      toast(payload.error || "Payment failed");
      return false;
    }
    if (!payload.payment?.token) {
      toast("Payment could not be started");
      return false;
    }
    const confirmation = await fetch(
      `${API_BASE}/api/orders/${id}/payment-confirm`,
      {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ paymentToken: payload.payment.token }),
      },
    );
    const confirmed = (await confirmation.json()) as {
      orders?: Order[];
      error?: string;
    };
    if (!confirmation.ok) {
      toast(confirmed.error || "Payment could not be confirmed");
      return false;
    }
    const changed = confirmed.orders?.[0];
    if (changed)
      setSharedOrders((orders) =>
        orders.map((order) => (order.id === id ? changed : order)),
      );
    toast("Payment successful. Your order is being prepared.");
    return true;
  };
  const shipSharedOrder = async (id: string, draft: ShipmentDraft) => {
    const response = await fetch(`${API_BASE}/api/orders/${id}/ship`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(draft),
    });
    const payload = (await response.json()) as {
      orders?: Order[];
      error?: string;
    };
    if (!response.ok) {
      toast(payload.error || "发货失败");
      return false;
    }
    const changed = payload.orders?.[0];
    if (changed)
      setSharedOrders((orders) =>
        orders.map((order) => (order.id === id ? changed : order)),
      );
    toast("已发货，物流单号已同步");
    return true;
  };
  const addShipmentEvent = async (
    id: string,
    label: string,
    detail: string,
  ) => {
    const response = await fetch(
      `${API_BASE}/api/orders/${id}/shipment-events`,
      {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ label, detail }),
      },
    );
    const payload = (await response.json()) as {
      orders?: Order[];
      error?: string;
    };
    if (!response.ok) {
      toast(payload.error || "物流更新失败");
      return false;
    }
    const changed = payload.orders?.[0];
    if (changed)
      setSharedOrders((orders) =>
        orders.map((order) => (order.id === id ? changed : order)),
      );
    toast("物流节点已更新");
    return true;
  };
  const updateSharedOrder = async (
    id: string,
    action: "receive" | "cancel",
  ) => {
    const response = await fetch(`${API_BASE}/api/orders/${id}/${action}`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    });
    const payload = (await response.json()) as {
      orders?: Order[];
      error?: string;
    };
    if (!response.ok) {
      toast(payload.error || "Order could not be updated");
      return false;
    }
    const changed = payload.orders?.[0];
    if (changed)
      setSharedOrders((orders) =>
        orders.map((order) => (order.id === id ? changed : order)),
      );
    return true;
  };
  const createAfterSale = async (id: string, draft: AfterSaleDraft) => {
    const response = await fetch(`${API_BASE}/api/orders/${id}/after-sales`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(draft),
    });
    const payload = (await response.json()) as {
      afterSales?: AfterSaleRequest[];
      error?: string;
    };
    if (!response.ok) {
      toast(payload.error || "Support request could not be submitted");
      return false;
    }
    setSharedAfterSales((items) => [...(payload.afterSales || []), ...items]);
    await refreshSharedOrders();
    toast("Support request submitted");
    return true;
  };
  const createReview = async (id: string, draft: ReviewDraft) => {
    const response = await fetch(`${API_BASE}/api/orders/${id}/review`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(draft),
    });
    const payload = (await response.json()) as {
      orders?: Order[];
      error?: string;
    };
    if (!response.ok) {
      toast(payload.error || "Review could not be submitted");
      return false;
    }
    const changed = payload.orders?.[0];
    if (changed)
      setSharedOrders((orders) =>
        orders.map((order) => (order.id === id ? changed : order)),
      );
    await refreshSharedOrders();
    toast("Review submitted");
    return true;
  };
  const createReviewFollowup = async (
    reviewIds: Array<string | number>,
    content: string,
  ) => {
    const responses = await Promise.all(
      reviewIds.map(async (reviewId) => {
        const response = await fetch(
          `${API_BASE}/api/reviews/${reviewId}/followup`,
          {
            method: "POST",
            credentials: "include",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ content }),
          },
        );
        const payload = (await response.json()) as { error?: string };
        return { ok: response.ok, error: payload.error };
      }),
    );
    const failed = responses.find((result) => !result.ok);
    if (failed) {
      toast(failed.error || "Follow-up could not be submitted");
      return false;
    }
    await refreshSharedOrders();
    toast("Follow-up submitted");
    return true;
  };
  const resolveAfterSale = async (
    id: string | number,
    action: "approve" | "reject",
    responseText: string,
  ) => {
    const response = await fetch(
      `${API_BASE}/api/after-sales/${id}/${action}`,
      {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ response: responseText.trim() }),
      },
    );
    const payload = (await response.json()) as {
      afterSales?: AfterSaleRequest[];
      error?: string;
    };
    if (!response.ok) {
      toast(payload.error || "售后处理失败");
      return false;
    }
    const changed = payload.afterSales?.[0];
    if (changed)
      setSharedAfterSales((items) =>
        items.map((item) => (item.id === id ? changed : item)),
      );
    await refreshSharedOrders();
    toast(action === "approve" ? "售后处理已提交" : "售后申请已拒绝");
    return true;
  };
  const submitReturnShipment = async (
    id: string | number,
    draft: ReturnShipmentDraft,
  ) => {
    const response = await fetch(
      `${API_BASE}/api/after-sales/${id}/return-shipment`,
      {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(draft),
      },
    );
    const payload = (await response.json()) as {
      afterSales?: AfterSaleRequest[];
      error?: string;
    };
    if (!response.ok) {
      toast(payload.error || "Return shipment could not be submitted");
      return false;
    }
    const changed = payload.afterSales?.[0];
    if (changed)
      setSharedAfterSales((items) =>
        items.map((item) => (item.id === id ? changed : item)),
      );
    await refreshSharedOrders();
    toast("Return shipment submitted. Waiting for the maker to confirm receipt.");
    return true;
  };
  const receiveReturn = async (id: string | number, responseText: string) => {
    const response = await fetch(
      `${API_BASE}/api/after-sales/${id}/receive-return`,
      {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ response: responseText.trim() }),
      },
    );
    const payload = (await response.json()) as {
      afterSales?: AfterSaleRequest[];
      error?: string;
    };
    if (!response.ok) {
      toast(payload.error || "确认收货失败");
      return false;
    }
    const changed = payload.afterSales?.[0];
    if (changed)
      setSharedAfterSales((items) =>
        items.map((item) => (item.id === id ? changed : item)),
      );
    await refreshSharedOrders();
    toast("已确认收货，退款已完成");
    return true;
  };
  const replySharedReview = async (id: string | number, reply: string) => {
    const response = await fetch(`${API_BASE}/api/reviews/${id}/reply`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reply }),
    });
    const payload = (await response.json()) as {
      reviews?: ProductReview[];
      error?: string;
    };
    if (!response.ok) {
      toast(payload.error || "评价回复失败");
      return false;
    }
    const changed = payload.reviews?.[0];
    if (changed)
      setSharedReviews((items) =>
        items.map((item) => (item.id === id ? changed : item)),
      );
    toast("评价回复已发送");
    return true;
  };
  const selected =
    data.products.find((p) => p.id === selectedId) || data.products[0];
  useEffect(() => {
    if (view === "studio") return;
    const titles: Record<MarketplaceView, string> = {
      home: "首页",
      discover: "发现好物",
      product: selected?.title || "作品详情",
      shop: "店铺",
      cart: "购物车",
      checkout: "结算",
      orders: "我的订单",
      favorites: "我的收藏",
      coupons: "优惠券",
      following: "关注店铺",
      messages: "消息中心",
      notifications: "通知",
      profile: "个人中心",
      security: "账号安全",
      community: "创作者社区",
      information: "帮助中心",
      studio: "卖家后台",
    };
    setDocumentTitle(titles[view]);
  }, [selected?.title, view]);
  const addToCart = (
    id: number,
    quantity = 1,
    variants: Record<string, string> = {},
  ) =>
    setData((v) => ({
      ...v,
      cart: v.cart.some(
        (i) =>
          i.productId === id &&
          JSON.stringify(i.variants || {}) === JSON.stringify(variants),
      )
        ? v.cart.map((i) =>
            i.productId === id &&
            JSON.stringify(i.variants || {}) === JSON.stringify(variants)
              ? {
                  ...i,
                  quantity: Math.min(
                    i.quantity + quantity,
                    (() => {
                      const product = v.products.find((p) => p.id === id);
                      return (
                        product?.skus?.find((sku) =>
                          Object.entries(variants).every(
                            ([name, value]) => sku.optionValues[name] === value,
                          ),
                        )?.stock ??
                        product?.stock ??
                        99
                      );
                    })(),
                  ),
                }
              : i,
          )
        : [
            ...v.cart,
            {
              productId: id,
              quantity: Math.min(
                quantity,
                v.products
                  .find((p) => p.id === id)
                  ?.skus?.find((sku) =>
                    Object.entries(variants).every(
                      ([name, value]) => sku.optionValues[name] === value,
                    ),
                  )?.stock ??
                  v.products.find((p) => p.id === id)?.stock ??
                  99,
              ),
              variants,
            },
          ],
    }));
  const updateSharedCart = async (
    id: number,
    quantity: number,
    variants: Record<string, string> = {},
  ) => {
    const product = data.products.find((item) => item.id === id);
    if (!product?.catalogId) return toast("This item is still syncing");
    const response = await fetch(`${API_BASE}/api/cart`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        catalogId: product.catalogId,
        quantity,
        variants,
        channel: trafficChannel,
      }),
    });
    if (!response.ok) return toast("Your bag could not be updated");
    applyBuyerState(await response.json());
  };
  const openProduct = (id: number) => {
    const product = data.products.find((item) => item.id === id);
    if (product?.catalogId)
      fetch(`${API_BASE}/api/analytics/events`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          type: "product_click",
          productId: product.catalogId,
          visitorKey,
          channel: trafficChannel,
          placement: "product_card",
          eventId: analyticsEventId(),
        }),
      }).catch(() => undefined);
    if (account.role === "buyer" && product?.analyticsShopId) {
      fetch(
        `${API_BASE}/api/analytics/shops/${product.analyticsShopId}/visits`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ visitorKey }),
        },
      ).catch(() => undefined);
    }
    show("product", { productId: id, returnView: view });
  };
  const openProductInNewTab = (id: number) => {
    const url = new URL(window.location.href);
    url.searchParams.set("product", String(id));
    url.searchParams.delete("view");
    url.searchParams.delete("tab");
    window.open(`${url.pathname}${url.search}${url.hash}`, "_blank", "noopener");
  };
  const applyBuyerState = (
    state: Pick<AppData, "cart" | "favorites" | "followedShops">,
  ) => setData((current) => ({ ...current, ...state }));
  const toggleFavorite = async (id: number) => {
    const product = data.products.find((item) => item.id === id);
    if (!product?.catalogId) return toast("This item is still syncing");
    const response = await fetch(
      `${API_BASE}/api/favorites/${product.catalogId}`,
      {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: "{}",
      },
    );
    if (!response.ok) return toast("Saved items could not be updated");
    applyBuyerState(await response.json());
  };
  const toggleShopFollow = async (shop: FollowedShop) => {
    if (isGuest) return toast("Sign in to follow a shop");
    const product = data.products.find((item) => item.shopId === shop.id);
    const shopId =
      typeof shop.id === "string" ? shop.id : product?.analyticsShopId;
    if (!shopId) return toast("This shop is still syncing");
    const response = await fetch(`${API_BASE}/api/follows/${shopId}`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    });
    if (!response.ok) return toast("Following could not be updated");
    const state = (await response.json()) as Pick<
      AppData,
      "cart" | "favorites" | "followedShops"
    >;
    applyBuyerState(state);
    toast(
      state.followedShops.some((item) => String(item.id) === String(shopId))
        ? "Shop followed"
        : "Shop unfollowed",
    );
  };
  const uploadShopPageImage = async (
    field: "avatar" | "banner",
    file?: File,
  ) => {
    if (!file) return;
    try {
      const dataUrl = await compressImageForUpload(file);
      const response = await fetch(`${API_BASE}/api/media`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          data: dataUrl,
          mediaType: "image",
          visibility: "public",
        }),
      });
      const payload = (await response.json().catch(() => ({}))) as {
        url?: string;
        error?: string;
      };
      if (!response.ok || !payload.url)
        throw new Error(payload.error || "图片上传失败");
      const imageUrl = payload.url.startsWith("/")
        ? `${API_BASE}${payload.url}`
        : payload.url;
      setData((current) => ({
        ...current,
        shop: { ...current.shop, [field]: imageUrl },
      }));
      toast(field === "avatar" ? "店铺头像已更新" : "店铺横幅已更新");
    } catch (error) {
      toast(error instanceof Error ? error.message : "图片上传失败");
    }
  };
  const nav = (target: typeof view, label: string) => {
    const href: Partial<Record<MarketplaceView, string>> = {
      home: "/",
      discover: "/discover/",
      studio: "/seller/dashboard/",
      shop: "/shop/",
      community: "/community/",
    };
    return (
    <button
      data-testid={`nav-${target}`}
      className={view === target ? "nav-active" : ""}
      onClick={() => {
        if (href[target]) {
          // Main navigation must keep the visitor in this application. Opening
          // a new tab left the original page unchanged and broke browser
          // navigation (including keyboard and assistive-technology flows).
          window.history.pushState({}, "", href[target]);
          window.dispatchEvent(new PopStateEvent("popstate"));
          return;
        }
        show(target);
      }}
    >
      {label}
    </button>
    );
  };
  if (!hydrated)
    return (
      <main
        className="app-loading"
        aria-busy="true"
        aria-label={englishPublicHeader ? "Loading marketplace" : "正在加载店铺数据"}
      >
        <span />
      </main>
    );
  const sellerWorkspace = account.role === "seller" && view === "studio";
  const sellerStorefront = account.role === "seller" && view === "shop";
  return (
    <div className={`app-shell${sellerWorkspace ? " seller-workspace-shell" : ""}`}>
      {!standaloneBrandEditor &&
        !sellerWorkspace &&
        !sellerStorefront &&
        view !== "community" &&
        view !== "messages" && (
        <div className="site-header">
          <div className="header-main container">
            <button
              className="brand"
              onClick={() => show("home")}
              aria-label={englishPublicHeader ? "Back to home" : "回到首页"}
            >
              {englishPublicHeader ? <>Shouzuo <span>Hub</span></> : <>手作<span>集</span></>}
            </button>
            {(account.role === "buyer" || account.role === "seller") && (
              <div className="search" ref={searchRef}>
                <Search size={19} />
                <input
                  value={query}
                  onFocus={() => setSearchOpen(true)}
                  onChange={(e) => {
                    setQuery(e.target.value);
                    setSearchOpen(true);
                  }}
                  onKeyDown={(e) => {
                    if (e.key === "Escape") setSearchOpen(false);
                    if (e.key === "Enter") {
                      setSearchOpen(false);
                      show("discover");
                    }
                  }}
                  placeholder={englishPublicHeader ? "Search handmade, original design, and vintage finds" : "搜索手作、原创设计、复古好物"}
                />
                <button
                  onClick={() => {
                    setSearchOpen(false);
                    show("discover");
                  }}
                >
                  {englishPublicHeader ? "Search" : "搜索"}
                </button>
                {searchOpen && query.trim() && searchSuggestions.length > 0 && (
                  <div
                    className="search-autocomplete"
                    role="listbox"
                    aria-label={englishPublicHeader ? "Search suggestions" : "搜索建议"}
                  >
                    {searchSuggestions.map((item) => (
                      <button
                        key={`${item.type}-${item.value}`}
                        role="option"
                        onMouseDown={(event) => event.preventDefault()}
                        onClick={() => {
                          setQuery(item.value);
                          setSearchSuggestions([]);
                          setSearchOpen(false);
                          show("discover");
                        }}
                      >
                        <span>{item.value}</span>
                        <small>{item.hint}</small>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}
            <div className="header-actions">
              {isGuest ? (
                <button
                  data-testid="open-auth"
                  className="logout-button"
                  onClick={onAuth}
                >
                  {englishPublicHeader ? "Sign in / Sign up" : "登录 / 注册"}
                </button>
              ) : (
                <>
                  <button
                    className="account-name-trigger"
                    onClick={() => show("profile")}
                  >
                    {account.name}
                  </button>
                  {account.role === "seller" && (
                    <div className="cart-wrap notification-menu-wrap">
                      <IconButton
                        icon={Bell}
                        label="消息通知"
                        active={notificationMenuOpen}
                        onClick={() => setNotificationMenuOpen((open) => !open)}
                      />
                      {notificationMenuOpen && (
                        <NotificationPopover notifications={notifications} conversationUnread={conversationUnread} onRead={markNotificationsRead} onReadAll={markAllNotificationsRead} onOpen={openNotification} onOpenMessages={() => { setNotificationMenuOpen(false); show("messages"); }} onViewAll={() => { setNotificationMenuOpen(false); show("notifications"); }} />
                      )}
                      {unifiedUnread > 0 && (
                        <span>
                          {unifiedUnread > 99 ? "99+" : unifiedUnread}
                        </span>
                      )}
                    </div>
                  )}
                  <IconButton icon={LogOut} label={englishPublicHeader ? "Sign out" : "退出"} onClick={onLogout} />
                </>
              )}
              {account.role === "buyer" && (
                <>
                  <div className="cart-wrap notification-menu-wrap">
                    <IconButton
                      icon={Bell}
                      label="Notifications"
                      active={notificationMenuOpen}
                      onClick={() => setNotificationMenuOpen((open) => !open)}
                    />
                    {notificationMenuOpen && (
                      <NotificationPopover notifications={notifications} conversationUnread={conversationUnread} onRead={markNotificationsRead} onReadAll={markAllNotificationsRead} onOpen={openNotification} onOpenMessages={() => { setNotificationMenuOpen(false); show("messages"); }} onViewAll={() => { setNotificationMenuOpen(false); show("notifications"); }} />
                    )}
                    {unifiedUnread > 0 && (
                      <span>{unifiedUnread > 99 ? "99+" : unifiedUnread}</span>
                    )}
                  </div>
                  <div className="cart-wrap">
                    <IconButton
                      icon={ShoppingBag}
                      label="Shopping bag"
                      testId="open-cart"
                      onClick={() => show("cart")}
                    />
                    {cartCount > 0 && (
                      <span data-testid="cart-count">{cartCount}</span>
                    )}
                  </div>
                </>
              )}
            </div>
          </div>
          <nav className="top-nav container">
            {account.role === "buyer" ? (
              <>
                {nav("home", "Home")}
                {nav("discover", "Discover")}
              </>
            ) : (
              <>
                {nav("home", "Home")}
                {nav("discover", "Discover")}
                {nav("studio", englishPublicHeader ? "Seller dashboard" : "店铺工作台")}
                {nav("shop", englishPublicHeader ? "Shop page" : "店铺主页")}
                {nav(
                  "community",
                  englishPublicHeader ? "Creator community" : "创作者社区",
                )}
              </>
            )}
          </nav>
        </div>
      )}
      <main
        className={
          sellerWorkspace
            ? "seller-workspace-main"
            : view === "messages"
              ? "messages-page-shell"
              : undefined
        }
      >
        {view === "home" && (
          <Home
            products={data.products.filter(
              (product) => product.listed !== false,
            )}
            favorites={data.favorites}
            onOpen={openProduct}
            onFavorite={toggleFavorite}
            onCategory={(c) => {
              show("discover", { category: c });
            }}
            onSellerRegistration={onSellerRegistration}
            sellerFacing={false}
          />
        )}
        {view === "community" && (
          <Suspense fallback={<main className="app-loading" aria-busy="true"><span /></main>}>
            <LazyCreatorCommunity
              accountName={isGuest ? "" : account.name}
              compressImageForUpload={compressImageForUpload}
            />
          </Suspense>
        )}
        {view === "information" && (
          <Suspense fallback={<main className="app-loading" aria-busy="true"><span /></main>}>
            <LazyPlatformInfoPage
              page={footerPage}
              onBack={() => show(account.role === "seller" ? "studio" : "home")}
            />
          </Suspense>
        )}
        {view === "discover" && (
          <Discover
            products={
              searchResults ??
              data.products.filter((product) => product.listed !== false)
            }
            personalizedProducts={personalizedProducts}
            query={query}
            searchMeta={searchMeta}
            serverFiltered={searchResults !== null}
            category={category}
            sort={searchSort}
            favorites={data.favorites}
            onOpen={openProduct}
            onFavorite={toggleFavorite}
            onCategory={(nextCategory) =>
              show("discover", { category: nextCategory })
            }
            onSort={setSearchSort}
            onQueryChange={setQuery}
            sellerFacing={false}
          />
        )}
        {view === "product" && (
          <Suspense fallback={<main className="app-loading" aria-busy="true"><span /></main>}>
            <LazyProductDetail
              context={{
                product: selected,
                products: data.products,
                favorite: data.favorites.includes(selected.id),
                onFavorite: toggleFavorite,
                favorites: data.favorites,
                onOpen: openProduct,
                shopFollowed: data.followedShops.some(
                  (shop) => String(shop.id) === String(selected.analyticsShopId),
                ),
                onToggleShopFollow: () =>
                  toggleShopFollow({
                    id: selected.analyticsShopId || selected.shopId,
                    name: selected.shop,
                  }),
                onAdd: (quantity: number, variants: Record<string, string>) => {
                  void updateSharedCart(selected.id, quantity, variants);
                  toast("Added to your bag");
                },
                onBuy: (quantity: number, variants: Record<string, string>) => {
                  void (async () => {
                    await updateSharedCart(selected.id, quantity, variants);
                    show("checkout");
                  })();
                },
                onContact: async () => {
                  if (isGuest || !selected.analyticsShopId) {
                    toast("Sign in to contact the maker");
                    return;
                  }
                  const response = await fetch(`${API_BASE}/api/messages/buyer`, {
                    method: "POST",
                    credentials: "include",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                      shopId: selected.analyticsShopId,
                      type: "product",
                      productId: selected.catalogId,
                    }),
                  });
                  if (!response.ok) return toast("Message could not be sent");
                  show("messages");
                },
                onReport: async (reason: string, detail: string, evidence: string[]) => {
                  if (isGuest || !selected.catalogId) {
                    toast("Sign in to submit a report");
                    return false;
                  }
                  const response = await fetch(`${API_BASE}/api/reports`, {
                    method: "POST",
                    credentials: "include",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                      targetType: "product",
                      targetId: selected.catalogId,
                      reason,
                      detail,
                      evidence,
                    }),
                  });
                  const payload = (await response.json()) as { error?: string };
                  if (!response.ok) {
                    toast(payload.error || "Report could not be submitted");
                    return false;
                  }
                  toast("Your report has been submitted and will be reviewed shortly.");
                  return true;
                },
                apiBase: API_BASE,
                compressImageForUpload,
                buyerProductCopy,
                buyerProductTerm,
                swatchColor,
                productListImageUrl,
                money,
                IconButton,
                ProductGrid,
              }}
            />
          </Suspense>
        )}
        {account.role === "seller" && view === "shop" && (
          <Suspense fallback={<main className="app-loading" aria-busy="true"><span /></main>}>
            <LazyShopPage
              context={{
                shop: data.shop,
                products: data.products.filter(
                  (p) => p.shopId === 99 && p.listed !== false,
                ),
                onOpen: openProduct,
                onStudio: () => {
                  const url = new URL(window.location.href);
                  url.searchParams.set("view", "studio");
                  url.searchParams.set("tab", "products");
                  window.history.pushState(
                    { view: "studio", tab: "products" },
                    "",
                    `${url.pathname}${url.search}${url.hash}`,
                  );
                  show("studio");
                },
                onImageUpload: (field: "avatar" | "banner", file?: File) =>
                  void uploadShopPageImage(field, file),
                preview: shopPreview,
                defaultAvatarImage,
                shopBannerImage,
                buyerShopName,
                buyerShopLocation,
                ProductGrid,
                Empty,
              }}
            />
          </Suspense>
        )}
        {account.role === "buyer" && view === "cart" && (
          <Cart
            data={data}
            onUpdate={(id, quantity, variants = {}) =>
              void updateSharedCart(id, quantity, variants)
            }
            onCheckout={() => show("checkout")}
            onDiscover={() => show("discover")}
          />
        )}
        {account.role === "buyer" && view === "checkout" && (
          <Checkout
            data={data}
            addresses={addresses}
            onQuote={quoteCheckout}
            onAddAddress={async (address) => {
              const response = await fetch(`${API_BASE}/api/addresses`, {
                method: "POST",
                credentials: "include",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(address),
              });
              const payload = (await response.json()) as {
                address?: BuyerAddress;
                error?: string;
              };
              if (!response.ok)
                throw new Error(payload.error || "Address could not be saved");
              setAddresses((items) => [
                payload.address!,
                ...items.map((item) => ({ ...item, isDefault: false })),
              ]);
              return payload.address!;
            }}
            onBack={() => show("cart")}
            onFinish={async (paymentMethod, addressId) => {
              const created = await createSharedOrders(
                addressId,
                paymentMethod,
              );
              if (!created?.length) return;
              const results = await Promise.all(
                created.map((order) => paySharedOrder(order.id, paymentMethod)),
              );
              if (results.every(Boolean)) toast("Payment successful. Your order is now being prepared.");
              else toast("Your order was created. Continue payment from Orders.");
              show("orders");
            }}
          />
        )}
        {account.role === "buyer" && view === "coupons" && (
          <main className="container page section">
            <div className="page-title">
              <div>
                <h1>Coupons</h1>
                <p>Claim coupons here. Your best available offer will be applied at checkout.</p>
              </div>
            </div>
            <section className="coupon-grid">
              {claimableCoupons.map((coupon) => (
                <article key={coupon.id}>
                  <b>{coupon.name}</b>
                  <strong>
                    Spend {money(coupon.threshold)}, save {money(coupon.discount)}
                  </strong>
                  <small>Limit {coupon.claimLimit} per customer</small>
                  <button
                    className="primary"
                    onClick={async () => {
                      const response = await fetch(
                        `${API_BASE}/api/campaigns/${coupon.id}/claim`,
                        {
                          method: "POST",
                          credentials: "include",
                          headers: { "Content-Type": "application/json" },
                          body: "{}",
                        },
                      );
                      if (response.ok) {
                        const payload = (await response.json()) as {
                          coupons: typeof coupons;
                        };
                        setCoupons(payload.coupons);
                        await refreshCoupons();
                        toast("Coupon claimed");
                      } else toast("Coupon could not be claimed or the limit has been reached");
                    }}
                  >
                    Claim coupon
                  </button>
                </article>
              ))}
              {!claimableCoupons.length && <p>No coupons are available right now.</p>}
            </section>
            <section className="studio-panel coupon-wallet">
              <div className="panel-head">
                <h2>My coupons</h2>
                <span>
                  {coupons.filter((coupon) => coupon.available).length} available
                </span>
              </div>
              {coupons.map((coupon) => (
                <article key={coupon.id}>
                  <span>
                    <b>{coupon.name}</b>
                    <small>
                      Spend {money(coupon.threshold)}, save {money(coupon.discount)} ·
                      {coupon.remaining} remaining
                    </small>
                  </span>
                  <strong className={coupon.available ? "coupon-active" : ""}>
                    {coupon.available ? "Available" : "Used or expired"}
                  </strong>
                </article>
              ))}
              {!coupons.length && <p>You have not claimed any coupons yet.</p>}
            </section>
          </main>
        )}
        {account.role === "buyer" && view === "orders" && (
          <Suspense fallback={<main className="app-loading" aria-busy="true"><span /></main>}>
          <LazyOrdersPage
            data={data}
            orders={sharedOrders}
            afterSales={sharedAfterSales}
            reviews={sharedReviews}
            compressImageForUpload={compressImageForUpload}
            productListImageUrl={productListImageUrl}
            buyerProductCopy={buyerProductCopy}
            buyerProductTerm={buyerProductTerm}
            buyerOrderStatusLabel={buyerOrderStatusLabel}
            onShipping={(id) => {
              setShippingId(id);
              setShippingModalOpen(true);
            }}
            onReceive={async (id) => {
              if (await updateSharedOrder(id, "receive")) toast("Delivery confirmed");
            }}
            onCancel={async (id) => {
              if (await updateSharedOrder(id, "cancel"))
                toast("Order cancelled and inventory restored");
            }}
            onPay={paySharedOrder}
            onReview={createReview}
            onFollowup={createReviewFollowup}
            onAfterSale={createAfterSale}
            onReturnShipment={submitReturnShipment}
          />
          </Suspense>
        )}
        {account.role === "buyer" && view === "following" && (
          <Suspense fallback={<main className="app-loading" aria-busy="true"><span /></main>}>
            <LazyFollowingShops
              shops={data.followedShops}
              onDiscover={() => show("discover")}
              onUnfollow={toggleShopFollow}
            />
          </Suspense>
        )}
        {account.role === "buyer" && view === "favorites" && (
          <Suspense fallback={<main className="app-loading" aria-busy="true"><span /></main>}>
            <LazyFavoritesPage
              products={data.products.filter(
                (product) => product.listed !== false,
              )}
              favorites={data.favorites}
              onOpen={openProduct}
              onFavorite={toggleFavorite}
              onDiscover={() => show("discover")}
              renderProductGrid={(products, favorites, onOpen, onFavorite) => (
                <ProductGrid
                  products={products as Product[]}
                  favorites={favorites}
                  onOpen={onOpen}
                  onFavorite={onFavorite}
                  openInNewTab
                  placement="favorite_list"
                />
              )}
            />
          </Suspense>
        )}
        {view === "messages" && (
          <Suspense fallback={<main className="app-loading" aria-busy="true"><span /></main>}>
            <LazyMessagesPage
              role={account.role === "seller" ? "seller" : "buyer"}
              apiBase={API_BASE}
              compressImageForUpload={compressImageForUpload}
              productListImageUrl={productListImageUrl}
              onUnreadChange={setConversationUnread}
            />
          </Suspense>
        )}
        {view === "notifications" && (
          <Suspense fallback={<main className="app-loading" aria-busy="true"><span /></main>}>
            <LazyNotificationCenter
              notifications={notifications}
              onRead={async (ids) => {
              await fetch(`${API_BASE}/api/notifications/read`, {
                method: "POST",
                credentials: "include",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ ids }),
              });
              setNotifications((items) =>
                items.map((item) =>
                  ids.includes(item.id) ? { ...item, read: true } : item,
                ),
              );
              setNotificationUnread((value) => Math.max(0, value - ids.length));
            }}
            onReadAll={async () => {
              await fetch(`${API_BASE}/api/notifications/read`, {
                method: "POST",
                credentials: "include",
                headers: { "Content-Type": "application/json" },
                body: "{}",
              });
              setNotifications((items) =>
                items.map((item) => ({ ...item, read: true })),
              );
              setNotificationUnread(0);
            }}
            onOpenMessages={() => show("messages")}
              conversationUnread={conversationUnread}
              onOpen={(item) => {
              if (item.relatedType === "product") {
                const product = data.products.find(
                  (value) => value.catalogId === item.relatedId,
                );
                if (product) return openProductInNewTab(product.id);
              }
              if (item.relatedType === "shop")
                return show(account.role === "seller" ? "studio" : "messages");
              show(account.role === "seller" ? "studio" : "orders");
              }}
            />
          </Suspense>
        )}
        {!isGuest && view === "security" && (
          <Suspense fallback={<main className="app-loading" aria-busy="true"><span /></main>}>
            <LazyAccountSecurity
              account={account}
              onBack={() => show(account.role === "seller" ? "studio" : "home")}
            />
          </Suspense>
        )}
        {!isGuest && view === "profile" && (
          <Suspense fallback={<main className="app-loading" aria-busy="true"><span /></main>}>
            <LazyProfileSettings
              account={account}
              onBack={() => show(account.role === "seller" ? "studio" : "home")}
              onSecurity={() => show("security")}
              onFavorites={() => show("favorites")}
              onOrders={() => show("orders")}
              onCoupons={() => {
                void refreshCoupons();
                show("coupons");
              }}
              onFollowing={() => show("following")}
              onAccountUpdated={onAccountUpdated}
              onAccountDeleted={onAccountDeleted}
            />
          </Suspense>
        )}
        {account.role === "seller" && view === "studio" && (
          <Studio
            data={data}
            setData={setData}
            orders={sharedOrders}
            afterSales={sharedAfterSales}
            reviews={sharedReviews}
            analyticsShopId={`legacy-shop-${account.id}`}
            onOpen={openProduct}
            onShipping={(id) => {
              setShippingId(id);
              setShippingModalOpen(true);
            }}
            onShip={shipSharedOrder}
            onAddShipmentEvent={addShipmentEvent}
            onResolveAfterSale={resolveAfterSale}
            onReceiveReturn={receiveReturn}
            onReplyReview={replySharedReview}
            toast={toast}
          />
        )}
      </main>
      {shippingModalOpen && (
        <Suspense fallback={null}>
          <LazyShippingModal
            order={sharedOrders.find((order) => order.id === shippingId)}
            onClose={() => {
              setShippingModalOpen(false);
              setShippingId("");
            }}
          />
        </Suspense>
      )}
      {!sellerWorkspace && view !== "messages" && (
        <PlatformFooter
          sellerFacing={false}
          onInfo={(page) => {
            setFooterPage(page);
            show("information");
          }}
        />
      )}
      {notice && (
        <div className="toast">
          <Check size={17} />
          {notice}
        </div>
      )}
    </div>
  );
}

function PlatformFooter({
  className,
  onInfo,
  sellerFacing = false,
}: {
  className?: string;
  onInfo: (page: FooterPage) => void;
  sellerFacing?: boolean;
}) {
  const links: { page: FooterPage; label: string }[] = sellerFacing ? [
    { page: "about", label: "关于我们" },
    { page: "seller-guide", label: "创作者入驻" },
    { page: "returns", label: "退换政策" },
    { page: "custom-orders", label: "定制说明" },
    { page: "disputes", label: "纠纷处理" },
    { page: "shipping", label: "配送与关税" },
    { page: "privacy", label: "隐私政策" },
    { page: "terms", label: "服务条款" },
    { page: "cookies", label: "Cookie 政策" },
    { page: "help", label: "帮助中心" },
  ] : [
    { page: "about", label: "About" },
    { page: "seller-guide", label: "Sell with us" },
    { page: "returns", label: "Returns & refunds" },
    { page: "custom-orders", label: "Custom orders" },
    { page: "disputes", label: "Disputes" },
    { page: "shipping", label: "Shipping & duties" },
    { page: "privacy", label: "Privacy" },
    { page: "terms", label: "Terms" },
    { page: "cookies", label: "Cookies" },
    { page: "help", label: "Help center" },
  ];
  return (
    <footer className={className}>
      <div className="container footer-inner">
        <div className="footer-brand">
          <strong>{sellerFacing ? "手作集" : "Shouzuo Hub"}</strong>
          <span>{sellerFacing ? "发现值得被珍藏的原创手作。" : "Handmade pieces, thoughtfully discovered."}</span>
        </div>
        <nav className="footer-links" aria-label={sellerFacing ? "平台信息" : "Platform information"}>
          {links.map(({ page, label }) => (
            <button key={page} onClick={() => onInfo(page)}>
              {label}
            </button>
          ))}
        </nav>
      </div>
    </footer>
  );
}

function Home({
  products,
  favorites,
  onOpen,
  onFavorite,
  onCategory,
  onSellerRegistration,
  sellerFacing = false,
}: {
  products: Product[];
  favorites: number[];
  onOpen: (id: number) => void;
  onFavorite: (id: number) => void;
  onCategory: (c: Category | "全部") => void;
  onSellerRegistration: () => void;
  sellerFacing?: boolean;
}) {
  return (
    <>
      <section className="hero">
        <div className="hero-image" />
        <div className="hero-copy container">
          <p>{sellerFacing ? "原创手作，独一无二" : "HANDMADE, ORIGINAL, YOURS"}</p>
          <h1>
            {sellerFacing ? (
              <>为真正喜爱的生活<br />留出空间</>
            ) : (
              <>Make room for what<br />you truly love</>
            )}
          </h1>
          <span>{sellerFacing ? "从一件手作开始，遇见让生活更有意义的创作者。" : "Start with a handmade piece, and meet the people who make life more meaningful."}</span>
          <button className="primary" onClick={() => onCategory("陶艺")}>
            {sellerFacing ? "选购手作" : "Shop handmade"} <ChevronRight size={18} />
          </button>
        </div>
      </section>
      <section className="container section">
        <div className="section-heading">
          <div>
              <p className="eyebrow home-section-eyebrow">{sellerFacing ? "为你精选" : "CURATED FOR YOU"}</p>
              <h2>{sellerFacing ? "发现适合每一种日常的手作" : "Discover handmade pieces for every kind of day"}</h2>
          </div>
          <button className="text-link" onClick={() => onCategory("全部")}>
            {sellerFacing ? "查看全部" : "View all"} <ChevronRight size={17} />
          </button>
        </div>
        <div className="category-grid discovery-category-grid">
          {discoveryCategories.slice(0, 6).map((c) => (
            <button
              className="category-tile"
              onClick={() => onCategory(c.name)}
              key={c.name}
            >
              <img src={c.image} alt="" />
              <span>{sellerFacing ? c.name : c.label}</span>
              <small>{sellerFacing ? "原创手作" : c.caption}</small>
            </button>
          ))}
        </div>
      </section>
      <section className="warm-section">
        <div className="container section">
          <div className="section-heading">
            <div>
              <p className="eyebrow home-section-eyebrow">{sellerFacing ? "本周精选" : "THIS WEEK'S PICKS"}</p>
              <h2>{sellerFacing ? "新品上架" : "New arrivals"}</h2>
            </div>
            <button className="text-link" onClick={() => onCategory("陶艺")}>
              {sellerFacing ? "发现更多" : "Discover more"} <ChevronRight size={17} />
            </button>
          </div>
          <div className="weekly-product-grid">
            <ProductGrid
              products={products.slice(0, 6)}
              favorites={favorites}
              onOpen={onOpen}
              onFavorite={onFavorite}
              openInNewTab={!sellerFacing}
              placement="home_new_arrivals"
              localizedForSeller={sellerFacing}
            />
          </div>
        </div>
      </section>
      <ActivityShowcase sellerFacing={sellerFacing} />
      <section className="maker-band">
        <div className="container maker-content">
          <div>
            <p className="eyebrow">{sellerFacing ? "为创作留一方天地" : "MAKE YOUR SPACE"}</p>
            <h2>{sellerFacing ? "你的创意，值得拥有成长的空间" : "Your creativity deserves a place to grow"}</h2>
            <p>{sellerFacing ? "展示作品、管理订单，轻松开始你的手作生意。" : "From showcasing your work to managing orders, start your handmade business with ease."}</p>
            <button className="outline-light" onClick={onSellerRegistration}>
              {sellerFacing ? "开始售卖" : "Start selling"} <ChevronRight size={18} />
            </button>
          </div>
          <div className="maker-stat">
            <strong>12,840</strong>
            <span>{sellerFacing ? "位独立创作者在这里分享作品" : "independent makers share their work here"}</span>
          </div>
        </div>
      </section>
    </>
  );
}

function ActivityShowcase({ sellerFacing = false }: { sellerFacing?: boolean }) {
  type Activity = {
    id: string;
    name: string;
    description: string;
    endsAt?: string;
    page: { banner?: string; theme?: { accent?: string }; modules?: string[] };
    products: {
      id: string;
      title: string;
      shop: string;
      image?: string;
      availableStock: number;
    }[];
  };
  const [activities, setActivities] = useState<Activity[]>([]);
  useEffect(() => {
    fetch(`${API_BASE}/api/activities`)
      .then((response) => (response.ok ? response.json() : Promise.reject()))
      .then((payload: { activities?: Activity[] }) =>
        setActivities(payload.activities || []),
      )
      .catch(() => undefined);
  }, []);
  if (!activities.length) return null;
  return (
    <section className="container section activity-showcase">
      {activities.slice(0, 2).map((activity) => (
        <article
          key={activity.id}
          style={{ borderColor: activity.page.theme?.accent || "#e66020" }}
        >
          <div
            className="activity-showcase-banner"
            style={
              activity.page.banner
                ? { backgroundImage: `url(${activity.page.banner})` }
                : { backgroundColor: activity.page.theme?.accent || "#e66020" }
            }
          >
            <span>{activity.page.modules?.join(" · ") || (sellerFacing ? "精选活动" : "Featured event")}</span>
            <h2>{activity.name}</h2>
            <p>{activity.description}</p>
            {activity.endsAt && <small>{sellerFacing ? `截至 ${activity.endsAt}` : `Ends ${activity.endsAt}`}</small>}
          </div>
          <div className="activity-showcase-products">
            {activity.products.slice(0, 4).map((product) => (
              <div key={product.id}>
                {product.image && (
                  <img
                    loading="lazy"
                    decoding="async"
                    src={productListImageUrl(product.image, 400)}
                    alt={sellerFacing ? product.title : buyerProductCopies[product.id]?.title || product.title}
                  />
                )}
                <b>{sellerFacing ? product.title : buyerProductCopies[product.id]?.title || product.title}</b>
                <small>
                  {sellerFacing ? `剩余 ${product.availableStock} 件` : `${product.availableStock} left`}
                </small>
              </div>
            ))}
          </div>
        </article>
      ))}
    </section>
  );
}

export function Discover({
  products,
  personalizedProducts = [],
  query,
  searchMeta = { originalQuery: "", recommendations: [] },
  serverFiltered = false,
  category,
  sort,
  favorites,
  onOpen,
  onFavorite,
  onCategory,
  onSort,
  onQueryChange = () => undefined,
  sellerFacing = false,
}: {
  products: Product[];
  personalizedProducts?: Product[];
  query: string;
  searchMeta?: {
    originalQuery: string;
    corrected?: string | null;
    recommendations: string[];
    zeroResult?: { message: string; productId?: string | null } | null;
  };
  serverFiltered?: boolean;
  category: Category | "全部";
  sort: "relevance" | "latest" | "price_asc" | "price_desc" | "sales";
  favorites: number[];
  onOpen: (id: number) => void;
  onFavorite: (id: number) => void;
  onCategory: (c: Category | "全部") => void;
  onSort: (
    sort: "relevance" | "latest" | "price_asc" | "price_desc" | "sales",
  ) => void;
  onQueryChange?: (query: string) => void;
  sellerFacing?: boolean;
}) {
  const [priceBand, setPriceBand] = useState<"" | "under_100" | "100_300" | "over_300">("");
  const [priceMin, setPriceMin] = useState("");
  const [priceMax, setPriceMax] = useState("");
  const [destination, setDestination] = useState("");
  const [freeShippingOnly, setFreeShippingOnly] = useState(false);
  const [deliveryDays, setDeliveryDays] = useState("");
  const [customOnly, setCustomOnly] = useState(false);
  const [readyToShipOnly, setReadyToShipOnly] = useState(false);
  const [topRatedOnly, setTopRatedOnly] = useState(false);
  const [craftsmanship, setCraftsmanship] = useState("");
  const [material, setMaterial] = useState("");
  const [color, setColor] = useState("");
  const [style, setStyle] = useState("");
  const [origin, setOrigin] = useState("");
  const copy = sellerFacing ? {
    home: "首页", discover: "发现好物", all: "全部", result: "搜索结果", pieces: "件独立创作者的手作作品", relevance: "综合排序", latest: "最新上架", sales: "销量优先", low: "价格从低到高", high: "价格从高到低", categories: "浏览分类", clear: "清除筛选", price: "价格", customPrice: "自定义价格（USD）", shipping: "配送", destination: "配送目的地", allDestinations: "全部目的地", freeShipping: "支持满额免邮", anyDelivery: "不限时效", within10: "10 天内送达", within14: "14 天内送达", within21: "21 天内送达", details: "商品状态", customizable: "支持定制", ready: "现货可发", rating: "4 星及以上（有评价）", craft: "手作属性", technique: "制作工艺", material: "主要材料", color: "颜色", style: "风格 / 标签", origin: "创作者所在地", allOrigins: "全部所在地", entered: "输入关键词筛选", related: "相关搜索", showing: "为你展示", picked: "为你推荐", pickedCopy: "基于浏览、收藏、购物袋和购买记录推荐。",
  } : {
    home: "Home", discover: "Discover", all: "All", result: "Search results", pieces: "handmade pieces from independent makers", relevance: "Relevance", latest: "Newest", sales: "Best selling", low: "Price: low to high", high: "Price: high to low", categories: "Browse categories", clear: "Clear filters", price: "Price", customPrice: "Custom price (USD)", shipping: "Shipping", destination: "Ship to", allDestinations: "All destinations", freeShipping: "Free shipping over threshold", anyDelivery: "Any delivery time", within10: "Arrives within 10 days", within14: "Arrives within 14 days", within21: "Arrives within 21 days", details: "Product details", customizable: "Customizable", ready: "Ready to ship", rating: "4 stars & up (with reviews)", craft: "Handmade details", technique: "Craft technique", material: "Material", color: "Color", style: "Style / tags", origin: "Maker location", allOrigins: "All locations", entered: "Enter a keyword to filter", related: "Related searches", showing: "Showing results for", picked: "Picked for you", pickedCopy: "Recommendations based on your browsing, saves, cart, and purchases.",
  };
  const origins = useMemo(() => Array.from(new Set(products.map((product) => product.shippingOrigin?.trim()).filter(Boolean))) as string[], [products]);
  const searchText = (product: Product) => [product.title, product.description, product.material, product.craftsmanship || "", ...(product.tags || []), ...(product.seoTags || []), ...(product.variants || []).flatMap((variant) => [variant.name, ...variant.values])].join(" ").toLowerCase();
  const eligibleZones = (product: Product) => (product.shippingTemplate?.zones || []).filter((zone) => zone.enabled && (!destination || zone.countries.includes(destination)));
  const baseFiltered = products.filter(
    (p) =>
      (category === "全部" || categoryMatchesProduct(category, p.category)) &&
      (serverFiltered ||
        !query ||
        `${p.title}${buyerProductCopy(p).title}${buyerProductCopy(p).description}${p.tags.join("")}${p.seoTags?.join("") || ""}`.toLowerCase().includes(
          query.toLowerCase(),
        )),
  );
  const filtered = baseFiltered.filter((product) => {
    const zones = eligibleZones(product);
    const text = searchText(product);
    const min = Number(priceMin), max = Number(priceMax);
    if (priceBand === "under_100" && product.price >= 100) return false;
    if (priceBand === "100_300" && (product.price < 100 || product.price > 300)) return false;
    if (priceBand === "over_300" && product.price < 300) return false;
    if (priceMin && (!Number.isFinite(min) || product.price < min)) return false;
    if (priceMax && (!Number.isFinite(max) || product.price > max)) return false;
    if (destination && !zones.length) return false;
    if (freeShippingOnly && !zones.some((zone) => Number(zone.freeShippingThreshold) > 0)) return false;
    if (deliveryDays && !zones.some((zone) => zone.maxDeliveryDays <= Number(deliveryDays))) return false;
    if (customOnly && !product.custom) return false;
    if (readyToShipOnly && product.stock <= 0) return false;
    if (topRatedOnly && !(product.reviews > 0 && product.rating >= 4)) return false;
    if (craftsmanship.trim() && !product.craftsmanship?.toLowerCase().includes(craftsmanship.trim().toLowerCase())) return false;
    if (material.trim() && !product.material.toLowerCase().includes(material.trim().toLowerCase())) return false;
    if (color.trim() && !text.includes(color.trim().toLowerCase())) return false;
    if (style.trim() && !text.includes(style.trim().toLowerCase())) return false;
    return !origin || product.shippingOrigin === origin;
  });
  const hasFilters = Boolean(priceBand || priceMin || priceMax || destination || freeShippingOnly || deliveryDays || customOnly || readyToShipOnly || topRatedOnly || craftsmanship || material || color || style || origin);
  const recommendations =
    !query &&
    category === "全部" &&
    searchMeta.recommendations.length === 0
      ? DEFAULT_DISCOVER_RECOMMENDATIONS
      : searchMeta.recommendations;
  const clearFilters = () => { setPriceBand(""); setPriceMin(""); setPriceMax(""); setDestination(""); setFreeShippingOnly(false); setDeliveryDays(""); setCustomOnly(false); setReadyToShipOnly(false); setTopRatedOnly(false); setCraftsmanship(""); setMaterial(""); setColor(""); setStyle(""); setOrigin(""); };
  const categoryLabel = (value: Category | "全部") => sellerFacing ? (value === "全部" ? copy.all : value) : buyerCategoryLabel(value);
  return (
    <div className="container page section">
      <div className="breadcrumbs">
        {copy.home} <ChevronRight size={14} /> {copy.discover}
      </div>
      <div className="discover-heading">
        <div>
          <h1>
            {query
              ? sellerFacing ? `${copy.result}：“${query}”` : `Search results for “${query}”`
              : category === "全部"
                ? sellerFacing ? "发现原创手作" : "Discover handmade"
                : categoryLabel(category)}
          </h1>
          <p>{sellerFacing ? `找到 ${filtered.length} ${copy.pieces}` : `${filtered.length} ${copy.pieces}`}</p>
        </div>
        <label className="search-sort">
          <SlidersHorizontal size={17} />
          <select
            aria-label={sellerFacing ? "排序方式" : "Sort results"}
            value={sort}
            onChange={(event) => onSort(event.target.value as typeof sort)}
          >
            <option value="relevance">{copy.relevance}</option>
            <option value="latest">{copy.latest}</option>
            <option value="sales">{copy.sales}</option>
            <option value="price_asc">{copy.low}</option>
            <option value="price_desc">{copy.high}</option>
          </select>
        </label>
      </div>
      {(searchMeta.corrected ||
        recommendations.length > 0 ||
        searchMeta.zeroResult) && (
        <section className="search-guidance">
          {searchMeta.corrected && (
            <p>{copy.showing} “{sellerFacing ? searchMeta.corrected : buyerSearchLabel(searchMeta.corrected)}”</p>
          )}
          {searchMeta.zeroResult && (
            <p className="search-zero-result">
              {searchMeta.zeroResult.message}
            </p>
          )}
          {recommendations.length > 0 && (
            <div>
              <span>{copy.related}</span>
              {recommendations.map((item) => (
                <button key={item} onClick={() => onQueryChange(item)}>
                  {sellerFacing ? item : buyerSearchLabel(item)}
                </button>
              ))}
            </div>
          )}
        </section>
      )}
      <div className="discover-layout">
        <aside className="discover-filters">
          <div className="discover-filter-heading">
            <strong>{copy.categories}</strong>
            {hasFilters && <button type="button" onClick={clearFilters}>{copy.clear}</button>}
          </div>
          <div className="discovery-category-list">
            {(["全部", ...discoveryCategories.map((c) => c.name)] as (
              | Category
              | "全部"
            )[]).map((c) => (
              <button
                key={c}
                className={c === category ? "selected" : ""}
                onClick={() => onCategory(c)}
              >
                {categoryLabel(c)}
              </button>
            ))}
          </div>
          <details className="discover-filter-group" open>
            <summary>{copy.price}</summary>
            {([['under_100', '$0 – $100'], ['100_300', '$100 – $300'], ['over_300', '$300+']] as const).map(([value, label]) => <label key={value}><input type="checkbox" checked={priceBand === value} onChange={() => { setPriceBand(priceBand === value ? "" : value); setPriceMin(""); setPriceMax(""); }} /> {label}</label>)}
            <span className="discover-price-inputs"><input inputMode="decimal" type="number" min="0" placeholder="Min" value={priceMin} onChange={(event) => { setPriceMin(event.target.value); setPriceBand(""); }} /><span>–</span><input inputMode="decimal" type="number" min="0" placeholder="Max" value={priceMax} onChange={(event) => { setPriceMax(event.target.value); setPriceBand(""); }} /></span>
            <small>{copy.customPrice}</small>
          </details>
          <details className="discover-filter-group" open>
            <summary>{copy.shipping}</summary>
            <select value={destination} onChange={(event) => setDestination(event.target.value)}><option value="">{copy.allDestinations}</option><option value="US">{sellerFacing ? "美国" : "United States"}</option><option value="CA">{sellerFacing ? "加拿大" : "Canada"}</option><option value="GB">{sellerFacing ? "英国" : "United Kingdom"}</option><option value="DE">{sellerFacing ? "德国" : "Germany"}</option><option value="FR">{sellerFacing ? "法国" : "France"}</option><option value="IT">{sellerFacing ? "意大利" : "Italy"}</option><option value="ES">{sellerFacing ? "西班牙" : "Spain"}</option></select>
            <label><input type="checkbox" checked={freeShippingOnly} onChange={(event) => setFreeShippingOnly(event.target.checked)} /> {copy.freeShipping}</label>
            <select value={deliveryDays} onChange={(event) => setDeliveryDays(event.target.value)}><option value="">{copy.anyDelivery}</option><option value="10">{copy.within10}</option><option value="14">{copy.within14}</option><option value="21">{copy.within21}</option></select>
          </details>
          <details className="discover-filter-group" open>
            <summary>{copy.details}</summary>
            <label><input type="checkbox" checked={customOnly} onChange={(event) => setCustomOnly(event.target.checked)} /> {copy.customizable}</label>
            <label><input type="checkbox" checked={readyToShipOnly} onChange={(event) => setReadyToShipOnly(event.target.checked)} /> {copy.ready}</label>
            <label><input type="checkbox" checked={topRatedOnly} onChange={(event) => setTopRatedOnly(event.target.checked)} /> {copy.rating}</label>
          </details>
          <details className="discover-filter-group">
            <summary>{copy.craft}</summary>
            <input value={craftsmanship} onChange={(event) => setCraftsmanship(event.target.value)} placeholder={`${copy.technique} · ${copy.entered}`} />
            <input value={material} onChange={(event) => setMaterial(event.target.value)} placeholder={`${copy.material} · ${copy.entered}`} />
            <input value={color} onChange={(event) => setColor(event.target.value)} placeholder={`${copy.color} · ${copy.entered}`} />
            <input value={style} onChange={(event) => setStyle(event.target.value)} placeholder={`${copy.style} · ${copy.entered}`} />
          </details>
          <details className="discover-filter-group">
            <summary>{copy.origin}</summary>
            <select value={origin} onChange={(event) => setOrigin(event.target.value)}><option value="">{copy.allOrigins}</option>{origins.map((item) => <option key={item} value={item}>{item}</option>)}</select>
          </details>
        </aside>
        <ProductGrid
          products={filtered}
          favorites={favorites}
          onOpen={onOpen}
          onFavorite={onFavorite}
          openInNewTab={!sellerFacing}
          placement={query ? "search_results" : category === "全部" ? "discover_catalog" : "category_results"}
          localizedForSeller={sellerFacing}
        />
      </div>
      {!query && category === "全部" && personalizedProducts.length > 0 && (
        <section className="personalized-products">
          <div className="section-heading">
            <div>
              <h2>{copy.picked}</h2>
              <p>{copy.pickedCopy}</p>
            </div>
          </div>
          <ProductGrid
            products={personalizedProducts}
            favorites={favorites}
            onOpen={onOpen}
            onFavorite={onFavorite}
            openInNewTab={!sellerFacing}
            placement="personalized_recommendations"
            localizedForSeller={sellerFacing}
          />
        </section>
      )}
    </div>
  );
}

function ProductGrid({
  products,
  favorites,
  onOpen,
  onFavorite,
  shopLayout = false,
  featuredProductIds = [],
  openInNewTab = false,
  localizedForSeller = false,
  placement = "public_catalog",
}: {
  products: Product[];
  favorites: number[];
  onOpen: (id: number) => void;
  onFavorite: (id: number) => void;
  shopLayout?: boolean;
  featuredProductIds?: Array<string | number>;
  openInNewTab?: boolean;
  localizedForSeller?: boolean;
  placement?: string;
}) {
  const gridRef = useRef<HTMLDivElement | null>(null);
  const recordedExposures = useRef(new Set<string>());
  useEffect(() => {
    if (
      typeof window === "undefined" ||
      !("IntersectionObserver" in window) ||
      !gridRef.current
    )
      return;
    const pending = new Map<Element, number>();
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          const productId = (entry.target as HTMLElement).dataset.analyticsProductId;
          const key = `${placement}:${productId || ""}`;
          if (!productId || recordedExposures.current.has(key)) {
            observer.unobserve(entry.target);
            continue;
          }
          if (entry.isIntersecting && entry.intersectionRatio >= 0.5) {
            if (!pending.has(entry.target)) {
              pending.set(
                entry.target,
                window.setTimeout(() => {
                  pending.delete(entry.target);
                  if (recordedExposures.current.has(key)) return;
                  recordedExposures.current.add(key);
                  recordProductAnalytics([
                    {
                      type: "product_impression",
                      productId,
                      visitorKey: analyticsVisitorKey(),
                      placement,
                      channel: publicTrafficChannel(),
                      eventId: analyticsEventId(),
                    },
                  ]);
                  observer.unobserve(entry.target);
                }, 1000),
              );
            }
          } else {
            const timeout = pending.get(entry.target);
            if (timeout !== undefined) {
              window.clearTimeout(timeout);
              pending.delete(entry.target);
            }
          }
        }
      },
      { threshold: [0.5] },
    );
    const cards = gridRef.current.querySelectorAll<HTMLElement>(
      "[data-analytics-product-id]",
    );
    cards.forEach((card) => observer.observe(card));
    return () => {
      pending.forEach((timeout) => window.clearTimeout(timeout));
      observer.disconnect();
    };
  }, [products, placement]);
  const openProduct = (id: number) => {
    if (!openInNewTab) return onOpen(id);
    const product = products.find((item) => item.id === id);
    if (product?.catalogId)
      recordProductAnalytics([
        {
          type: "product_click",
          productId: product.catalogId,
          visitorKey: analyticsVisitorKey(),
          placement,
          channel: publicTrafficChannel(),
          eventId: analyticsEventId(),
        },
      ]);
    const url = new URL(window.location.href);
    url.searchParams.set("product", String(id));
    url.searchParams.delete("view");
    url.searchParams.delete("tab");
    window.open(
      `${url.pathname}${url.search}${url.hash}`,
      "_blank",
      "noopener",
    );
  };
  return (
    <div
      ref={gridRef}
      className={`product-grid${shopLayout ? " shop-product-grid" : ""}`}
    >
      {products.map((p) => {
        const sourceImage =
          bundledCatalogImages[p.catalogId || ""] ||
          bundledMediaImages[p.image] ||
          p.image;
        const thumbnail400 = productListImageUrl(sourceImage, 400);
        const thumbnail800 = productListImageUrl(sourceImage, 800);
        return (
        <article
          className="product-card"
          data-testid={`product-card-${p.catalogId || p.id}`}
          data-analytics-product-id={p.catalogId || undefined}
          key={p.id}
        >
          <div className="product-image" onClick={() => openProduct(p.id)}>
            <img
              loading="lazy"
              decoding="async"
              src={thumbnail400}
              srcSet={`${thumbnail400} 400w, ${thumbnail800} 800w`}
              sizes="(max-width: 640px) 50vw, (max-width: 980px) 33vw, 380px"
              alt={localizedForSeller ? p.title : buyerProductCopy(p).title}
            />
            {p.custom && <span className="custom-badge">{localizedForSeller ? "可定制" : "Custom"}</span>}
            {featuredProductIds.some(
              (id) => String(id) === String(p.catalogId || p.id),
            ) && (
              <span className="featured-badge">{localizedForSeller ? "推荐" : "Featured"}</span>
            )}
            <IconButton
              icon={Heart}
              label={localizedForSeller ? "收藏" : "Save"}
              active={favorites.includes(p.id)}
              onClick={(event) => {
                event.stopPropagation();
                onFavorite(p.id);
              }}
            />
          </div>
          <div className="product-info">
            <h3>
              <button
                data-testid={`product-open-${p.catalogId || p.id}`}
                className="product-title-link"
                title={localizedForSeller ? p.title : buyerProductCopy(p).title}
                onClick={() => openProduct(p.id)}
              >
                {localizedForSeller ? p.title : buyerProductCopy(p).title}
              </button>
            </h3>
            {shopLayout ? (
              <div className="shop-product-meta">
                <span className="shop-product-price">
                  <strong>{money(p.price)}</strong>
                  {p.oldPrice && <del>{money(p.oldPrice)}</del>}
                </span>
                <span className="rating">
                  <Star size={14} fill="currentColor" />
                  {p.rating} <small>({p.reviews})</small>
                </span>
              </div>
            ) : (
              <>
                <span className="rating">
                  <Star size={14} fill="currentColor" />
                  {p.rating} <small>({p.reviews})</small>
                </span>
                <strong>{money(p.price)}</strong>
                {p.oldPrice && <del>{money(p.oldPrice)}</del>}
              </>
            )}
          </div>
        </article>
        );
      })}
    </div>
  );
}

export function Cart({
  data,
  onUpdate,
  onCheckout,
  onDiscover,
}: {
  data: AppData;
  onUpdate: (id: number, q: number, variants?: Record<string, string>) => void;
  onCheckout: () => void;
  onDiscover: () => void;
}) {
  const items = data.cart.map((i) => ({
    ...i,
    product: data.products.find((p) => p.id === i.productId)!,
  }));
  const total = items.reduce((s, i) => s + i.product.price * i.quantity, 0);
  return (
    <div className="container page section">
      <h1>
        Shopping bag <small>{items.length} items</small>
      </h1>
      {items.length ? (
        <div className="cart-layout">
          <div className="cart-list">
            {items.map(({ product, quantity, variants }) => (
              <div
                className="cart-item"
                key={`${product.id}-${JSON.stringify(variants || {})}`}
              >
                <img src={productListImageUrl(product.image, 160)} alt="" />
                <div>
                  <h3>{buyerProductCopy(product).title}</h3>
                  {Object.keys(variants || {}).length > 0 && (
                    <small className="selected-specs">
                      {Object.entries(variants || {})
                        .map(
                          ([name, value]) =>
                            `${buyerProductTerm(name)}: ${buyerProductTerm(value)}`,
                        )
                        .join(" · ")}
                    </small>
                  )}
                  <span>{money(product.price)}</span>
                  <div className="qty-controls">
                    <IconButton
                      icon={Minus}
                      label="Decrease quantity"
                      onClick={() =>
                        onUpdate(product.id, quantity - 1, variants)
                      }
                    />
                    <b>{quantity}</b>
                    <IconButton
                      icon={Plus}
                      label="Increase quantity"
                      onClick={() =>
                        onUpdate(
                          product.id,
                          Math.min(
                            quantity + 1,
                            product.skus?.find((sku) =>
                              Object.entries(variants || {}).every(
                                ([name, value]) =>
                                  sku.optionValues[name] === value,
                              ),
                            )?.stock ?? product.stock,
                          ),
                          variants,
                        )
                      }
                    />
                  </div>
                </div>
                <button
                  className="remove"
                  onClick={() => onUpdate(product.id, 0, variants)}
                >
                  <X size={18} />
                  Remove
                </button>
              </div>
            ))}
          </div>
          <aside className="summary">
            <h3>Order summary</h3>
            <p>
              <span>Subtotal</span>
              <b>{money(total)}</b>
            </p>
            <p>
              <span>Shipping</span>
              <b>{money(0)}</b>
            </p>
            <hr />
            <p className="total">
              <span>Total</span>
              <b>{money(total)}</b>
            </p>
            <button
              data-testid="cart-checkout"
              className="primary full"
              onClick={onCheckout}
            >
              Checkout <ChevronRight size={18} />
            </button>
            <small>You will review and confirm payment on the next step.</small>
          </aside>
        </div>
      ) : (
        <Empty
          title="Your bag is empty"
          text="Find a handmade piece to make every day feel more special."
          action="Discover handmade"
          onAction={onDiscover}
        />
      )}
    </div>
  );
}

export function Checkout({
  data,
  addresses,
  onQuote,
  onAddAddress,
  onBack,
  onFinish,
}: {
  data: AppData;
  addresses: BuyerAddress[];
  onQuote: (addressId: string) => Promise<CheckoutQuote>;
  onAddAddress: (address: Omit<BuyerAddress, "id">) => Promise<BuyerAddress>;
  onBack: () => void;
  onFinish: (paymentMethod: PaymentMethod, addressId: string) => void;
}) {
  const [selectedAddressId, setSelectedAddressId] = useState("");
  const [quote, setQuote] = useState<CheckoutQuote | null>(null);
  const [addressDraft, setAddressDraft] = useState({
    recipient: "",
    phone: "",
    countryCode: "US",
    country: "United States",
    province: "",
    city: "",
    district: "",
    detail: "",
  });
  const [addressError, setAddressError] = useState("");
  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod>("alipay");
  useEffect(() => {
    if (!addresses.length) return;
    setSelectedAddressId(
      (current) =>
        current ||
        addresses.find((address) => address.isDefault)?.id ||
        addresses[0].id,
    );
  }, [addresses]);
  useEffect(() => {
    if (!selectedAddressId || !data.cart.length) return;
    setQuote(null);
    setAddressError("");
    void onQuote(selectedAddressId)
      .then(setQuote)
      .catch((error: Error) => setAddressError(error.message));
  }, [data.cart, onQuote, selectedAddressId]);
  const total = data.cart.reduce(
    (s, i) =>
      s +
      (data.products.find((p) => p.id === i.productId)?.price || 0) *
        i.quantity,
    0,
  );
  return (
    <div className="container page section">
      <button className="back" onClick={onBack}>
        <ArrowLeft size={18} />
        Back to bag
      </button>
      <h1>Checkout</h1>
      <div className="checkout-layout">
        <div className="checkout-main">
          <section>
            <h3>
              <MapPin size={19} />
                Delivery address
            </h3>
            <div className="address-list">
              {addresses.map((address) => (
                <label
                  className={`address ${selectedAddressId === address.id ? "selected-address" : ""}`}
                  key={address.id}
                >
                  <input
                    type="radio"
                    name="address"
                    checked={selectedAddressId === address.id}
                    onChange={() => setSelectedAddressId(address.id)}
                  />
                  <b>
                    {address.recipient} {address.phone}
                  </b>
                  <p>
                    {address.country} · {address.countryCode} ·
                    {address.province}
                    {address.city}
                    {address.district}
                    {address.detail}
                  </p>
                  {address.isDefault && <span>Default</span>}
                </label>
              ))}
            </div>
            <div className="address-editor">
              <select
                data-testid="checkout-country"
                value={addressDraft.countryCode}
                onChange={(event) => {
                  const countryCode = event.target.value;
                  const country = SHIPPING_COUNTRY_OPTIONS.find(([code]) => code === countryCode)?.[1] || "";
                  setAddressDraft((value) => ({ ...value, countryCode, country }));
                }}
              >
                {SHIPPING_COUNTRY_OPTIONS.map(([code, name]) => (
                  <option key={code} value={code}>{name}</option>
                ))}
              </select>
              <input
                data-testid="checkout-recipient"
                value={addressDraft.recipient}
                onChange={(event) =>
                  setAddressDraft((value) => ({
                    ...value,
                    recipient: event.target.value,
                  }))
                }
                placeholder="Recipient name"
              />
              <input
                data-testid="checkout-phone"
                value={addressDraft.phone}
                onChange={(event) =>
                  setAddressDraft((value) => ({
                    ...value,
                    phone: event.target.value,
                  }))
                }
                placeholder="Phone number"
              />
              <input
                data-testid="checkout-province"
                value={addressDraft.province}
                onChange={(event) =>
                  setAddressDraft((value) => ({
                    ...value,
                    province: event.target.value,
                  }))
                }
                placeholder="State / province"
              />
              <input
                data-testid="checkout-city"
                value={addressDraft.city}
                onChange={(event) =>
                  setAddressDraft((value) => ({
                    ...value,
                    city: event.target.value,
                  }))
                }
                placeholder="City"
              />
              <input
                data-testid="checkout-district"
                value={addressDraft.district}
                onChange={(event) =>
                  setAddressDraft((value) => ({
                    ...value,
                    district: event.target.value,
                  }))
                }
                placeholder="District"
              />
              <input
                data-testid="checkout-detail"
                value={addressDraft.detail}
                onChange={(event) =>
                  setAddressDraft((value) => ({
                    ...value,
                    detail: event.target.value,
                  }))
                }
                placeholder="Street address"
              />
              <button
                data-testid="checkout-add-address"
                className="secondary"
                type="button"
                onClick={async () => {
                  try {
                    const address = await onAddAddress({
                      ...addressDraft,
                      isDefault: !addresses.length,
                    });
                    setSelectedAddressId(address.id);
                    setAddressDraft({
                      recipient: "",
                      phone: "",
                      countryCode: "US",
                      country: "United States",
                      province: "",
                      city: "",
                      district: "",
                      detail: "",
                    });
                  } catch (error) {
                    setAddressError(
                      error instanceof Error ? error.message : "地址保存失败",
                    );
                  }
                }}
              >
                Add address
              </button>
            </div>
            {addressError && (
              <small className="checkout-error">{addressError}</small>
            )}
          </section>
          <section>
            <h3>
              <CreditCard size={19} />
              Payment method
            </h3>
            <label className="payment-option">
              <input
                type="radio"
                checked={paymentMethod === "alipay"}
                name="pay"
                onChange={() => setPaymentMethod("alipay")}
              />
              <span className="pay-icon">¥</span>
              <b>Alipay</b>
              <em>Recommended</em>
            </label>
            <label className="payment-option">
              <input
                type="radio"
                checked={paymentMethod === "card"}
                name="pay"
                onChange={() => setPaymentMethod("card")}
              />
              <span className="pay-icon card">▣</span>
              <b>Bank card</b>
            </label>
          </section>
          <section>
            <h3>
              <Package size={19} />
              Items in your order
            </h3>
            {data.cart.map((i) => {
              const p = data.products.find((x) => x.id === i.productId)!;
              return (
                <div
                  className="checkout-item"
                  key={`${p.id}-${JSON.stringify(i.variants || {})}`}
                >
                  <img src={productListImageUrl(p.image, 160)} alt="" />
                  <span>
                    {buyerProductCopy(p).title} × {i.quantity}
                    {Object.keys(i.variants || {}).length > 0 && (
                      <small className="selected-specs">
                        {Object.entries(i.variants || {})
                          .map(
                            ([name, value]) =>
                              `${buyerProductTerm(name)}: ${buyerProductTerm(value)}`,
                          )
                          .join(" · ")}
                      </small>
                    )}
                  </span>
                  <b>{money(p.price * i.quantity)}</b>
                </div>
              );
            })}
          </section>
        </div>
        <aside className="summary">
          <h3>Order total</h3>
          <p>
            <span>Subtotal</span>
            <b>{money(quote?.itemAmount ?? total)}</b>
          </p>
          <p>
            <span>Shipping</span>
            <b>{money(quote?.shippingAmount ?? 0)}</b>
          </p>
          <p>
            <span>Discount</span>
            <b>-{money(quote?.discountAmount ?? 0)}</b>
          </p>
          <p className="total">
            <span>Total</span>
            <b>{money(quote?.amount ?? total)}</b>
          </p>
          <small className="auth-hint">
            All prices and payments are in USD. The order rate is locked at {quote?.exchangeRate || "1.00000000"} USD/USD.
          </small>
          {quote?.shops?.map((shop) => shop.shippingRule && (
            <small className="auth-hint" key={shop.shopId}>
              {shop.shop}: {shop.shippingRule.carrier} · {shop.shippingRule.zoneName} · {shop.shippingRule.minDeliveryDays}–{shop.shippingRule.maxDeliveryDays} business days to {shop.shippingRule.destinationCountry}
            </small>
          ))}
          <button
            data-testid="checkout-submit"
            className="primary full"
            disabled={!selectedAddressId || !quote || Boolean(addressError)}
            onClick={() => onFinish(paymentMethod, selectedAddressId)}
          >
            Place order and pay
          </button>
        </aside>
      </div>
    </div>
  );
}

function Studio({
  data,
  setData,
  orders,
  afterSales,
  reviews,
  analyticsShopId,
  onOpen,
  onShipping,
  onShip,
  onAddShipmentEvent,
  onResolveAfterSale,
  onReceiveReturn,
  onReplyReview,
  toast,
}: {
  data: AppData;
  setData: React.Dispatch<React.SetStateAction<AppData>>;
  orders: Order[];
  afterSales: AfterSaleRequest[];
  reviews: ProductReview[];
  analyticsShopId: string;
  onOpen: (id: number) => void;
  onShipping: (id: string) => void;
  onShip: (id: string, draft: ShipmentDraft) => Promise<boolean>;
  onAddShipmentEvent: (
    id: string,
    label: string,
    detail: string,
  ) => Promise<boolean>;
  onResolveAfterSale: (
    id: string | number,
    action: "approve" | "reject",
    response: string,
  ) => Promise<boolean>;
  onReceiveReturn: (id: string | number, response: string) => Promise<boolean>;
  onReplyReview: (id: string | number, reply: string) => Promise<boolean>;
  toast: (s: string) => void;
}) {
  const studioTabs = [
    "overview",
    "products",
    "inventory",
    "orders",
    "messages",
    "reviews",
    "shipping",
    "service",
    "members",
    "support",
    "activities",
    "advisor",
    "promotions",
    "finance",
    "brand-site",
    "settings",
  ] as const;
  type StudioTab = (typeof studioTabs)[number];
  const initialStudioTab = new URLSearchParams(window.location.search).get(
    "tab",
  );
  const [tab, setTab] = useState<StudioTab>(() =>
    studioTabs.includes(initialStudioTab as StudioTab)
      ? (initialStudioTab as StudioTab)
      : "overview",
  );
  useEffect(() => {
    const titles: Record<StudioTab, string> = {
      overview: "卖家后台",
      products: "作品管理",
      inventory: "库存管理",
      orders: "订单管理",
      messages: "买家消息",
      reviews: "评价管理",
      shipping: "物流管理",
      service: "售后服务",
      members: "成员管理",
      support: "平台支持",
      activities: "营销活动",
      advisor: "经营顾问",
      promotions: "店铺营销",
      finance: "财务中心",
      "brand-site": "品牌站",
      settings: "店铺设置",
    };
    setDocumentTitle(titles[tab]);
  }, [tab]);
  const buyerPreviewUrl = (() => {
    const url = new URL(window.location.href);
    // This link is created from /seller/dashboard/. Updating only `view` leaves
    // the dashboard pathname intact, and pathname-based routing then opens the
    // seller console again instead of the buyer-facing storefront.
    url.pathname = "/shop/";
    url.search = new URLSearchParams({ shopPreview: "1" }).toString();
    url.hash = "";
    return url.toString();
  })();
  // The seller console is operated by Chinese-speaking merchants. Buyer-facing
  // pages are localized independently, while this workspace always stays Chinese.
  const studioText = (zh: string, _en: string) => zh;
  const sellerNavigationGroups = [
    {
      id: "catalog",
      label: "商品管理",
      items: [
        { id: "products" as StudioTab, label: "我的作品", Icon: Package },
        { id: "inventory" as StudioTab, label: "库存管理", Icon: SlidersHorizontal },
      ],
    },
    {
      id: "orders",
      label: "订单服务",
      items: [
        { id: "orders" as StudioTab, label: "订单管理", Icon: ShoppingBag },
        { id: "messages" as StudioTab, label: "买家消息", Icon: MessageCircle },
        { id: "reviews" as StudioTab, label: "评价管理", Icon: Star },
        { id: "shipping" as StudioTab, label: "运费管理", Icon: Truck },
      ],
    },
    {
      id: "growth",
      label: "经营增长",
      items: [
        { id: "advisor" as StudioTab, label: "数据参谋", Icon: Settings2 },
        { id: "activities" as StudioTab, label: "活动报名", Icon: Package },
        { id: "promotions" as StudioTab, label: "优惠管理", Icon: BadgePercent },
        { id: "finance" as StudioTab, label: "结算与资金", Icon: CreditCard },
        { id: "brand-site" as StudioTab, label: "我的独立站", Icon: Globe2 },
      ],
    },
    {
      id: "settings",
      label: "店铺管理",
      items: [
        { id: "service" as StudioTab, label: "资料与认证", Icon: UserRound },
        { id: "members" as StudioTab, label: "成员与权限", Icon: UserRound },
        { id: "support" as StudioTab, label: "客服工单", Icon: MessageCircle },
        { id: "settings" as StudioTab, label: "店铺设置", Icon: Store },
      ],
    },
  ] as const;
  const sellerNavigationGroupForTab = (next: StudioTab) =>
    sellerNavigationGroups.find((group) =>
      group.items.some((item) => item.id === next),
    );
  const [expandedSellerNavigationGroups, setExpandedSellerNavigationGroups] =
    useState<Record<string, boolean>>(() => {
      const activeGroup = sellerNavigationGroupForTab(tab);
      return activeGroup ? { [activeGroup.id]: true } : {};
    });
  const [messageUnread, setMessageUnread] = useState(0);
  const [messageSoundEnabled, setMessageSoundEnabled] = useState(() =>
    window.localStorage.getItem("seller-message-sound-enabled") !== "false",
  );
  const messageSoundEnabledRef = useRef(messageSoundEnabled);
  const lastMessageSoundAtRef = useRef(0);
  const [showForm, setShowForm] = useState(false);
  const [shipmentOrder, setShipmentOrder] = useState<Order | null>(null);
  const [shipmentEventOrder, setShipmentEventOrder] = useState<Order | null>(
    null,
  );
  const [afterSaleDecision, setAfterSaleDecision] = useState<{
    request: AfterSaleRequest;
    action: "approve" | "reject" | "receive";
  } | null>(null);
  const [replyingReviewId, setReplyingReviewId] = useState<
    string | number | null
  >(null);
  const [reviewReply, setReviewReply] = useState("");
  const sellerProducts = data.products.filter((p) => p.shopId === 99);
  const [productListMode, setProductListMode] = useState<"listed" | "trash">(
    "listed",
  );
  const listedSellerProducts = sellerProducts.filter((p) => p.listed !== false);
  const recycledSellerProducts = sellerProducts.filter(
    (p) => p.listed === false,
  );
  const sellerProductSelectionId = (product: Product) =>
    product.catalogId || String(product.id);
  const displayedSellerProducts =
    productListMode === "listed"
      ? listedSellerProducts
      : recycledSellerProducts;
  const [editingProductId, setEditingProductId] = useState<number | null>(null);
  const [editingProductCatalogId, setEditingProductCatalogId] = useState<
    string | null
  >(null);
  const [editingDraftId, setEditingDraftId] = useState<number | null>(null);
  const [editingDraftCatalogId, setEditingDraftCatalogId] = useState<
    string | null
  >(null);
  const [selectedProductIds, setSelectedProductIds] = useState<string[]>([]);
  const [aiAssistantOpen, setAiAssistantOpen] = useState(false);
  const [bulkPrice, setBulkPrice] = useState("");
  const [bulkStock, setBulkStock] = useState("");
  const [inventoryProductId, setInventoryProductId] = useState<number | null>(
    null,
  );
  const [inventorySkuId, setInventorySkuId] = useState("");
  const [inventorySearch, setInventorySearch] = useState("");
  const [inventorySearchOpen, setInventorySearchOpen] = useState(false);
  const [inventoryAdjustmentType, setInventoryAdjustmentType] = useState<
    "set" | "increase" | "decrease"
  >("increase");
  const [inventoryQuantity, setInventoryQuantity] = useState("");
  const [inventoryReason, setInventoryReason] = useState("");
  const [inventorySelectedSkuIds, setInventorySelectedSkuIds] = useState<
    string[]
  >([]);
  const [inventoryRowValues, setInventoryRowValues] = useState<
    Record<string, string>
  >({});
  const [inventoryListReason, setInventoryListReason] = useState("");
  const [inventoryAdjustments, setInventoryAdjustments] = useState<
    InventoryAdjustment[]
  >([]);
  const openStudioTab = (next: StudioTab) => {
    const group = sellerNavigationGroupForTab(next);
    if (group)
      setExpandedSellerNavigationGroups((current) => ({
        ...current,
        [group.id]: true,
      }));
    setTab(next);
    const url = new URL(window.location.href);
    url.searchParams.set("view", "studio");
    url.searchParams.set("tab", next);
    const nextUrl = `${url.pathname}${url.search}${url.hash}`;
    if (
      nextUrl !==
      `${window.location.pathname}${window.location.search}${window.location.hash}`
    )
      window.history.pushState({ view: "studio", tab: next }, "", nextUrl);
  };
  useEffect(() => {
    const syncTabFromLocation = () => {
      const next = new URLSearchParams(window.location.search).get("tab");
      const nextTab =
        studioTabs.includes(next as StudioTab)
          ? (next as StudioTab)
          : "overview";
      const group = sellerNavigationGroupForTab(nextTab);
      if (group)
        setExpandedSellerNavigationGroups((current) => ({
          ...current,
          [group.id]: true,
        }));
      setTab(nextTab);
    };
    window.addEventListener("popstate", syncTabFromLocation);
    return () => window.removeEventListener("popstate", syncTabFromLocation);
  }, []);
  const [form, setForm] = useState({
    title: "",
    buyerTitle: "",
    buyerDescription: "",
    buyerMaterial: "",
    buyerSeoTags: [] as string[],
    price: "",
    category: "陶艺陶瓷" as Category,
    stock: "10",
    weightGrams: "",
    dimensions: "",
    lowStockThreshold: "3",
    description: "",
    material: "",
    craftsmanship: "",
    images: [] as string[],
    imageAssetIds: [] as string[],
    video: "",
    videoAssetId: "",
    seoTags: [] as string[],
    custom: false,
  });
  const [seoTagInput, setSeoTagInput] = useState("");
  const [draggedImageIndex, setDraggedImageIndex] = useState<number | null>(
    null,
  );
  const [dragOverImageIndex, setDragOverImageIndex] = useState<number | null>(
    null,
  );
  const [pendingProductImageIds, setPendingProductImageIds] = useState<
    string[]
  >([]);
  const [pendingProductImageProgress, setPendingProductImageProgress] =
    useState<Record<string, number>>({});
  const [isGeneratingProductTitle, setIsGeneratingProductTitle] =
    useState(false);
  const [generatedChineseTitle, setGeneratedChineseTitle] = useState("");
  const [productImageLoadStates, setProductImageLoadStates] = useState<
    Record<string, "loading" | "loaded" | "error">
  >({});
  const [pendingVariantImageKeys, setPendingVariantImageKeys] = useState<
    string[]
  >([]);
  const [variantImageLoadStates, setVariantImageLoadStates] = useState<
    Record<string, "loading" | "loaded" | "error">
  >({});
  // This is an editable estimate until the platform has a contracted payment
  // provider. The actual charge always comes from the order settlement record.
  const [estimatedGatewayFeeRate, setEstimatedGatewayFeeRate] = useState("4.4");
  const [settlementEstimatorExpanded, setSettlementEstimatorExpanded] =
    useState(false);
  const productSaleAmount = Math.max(0, Number(form.price) || 0);
  const shippingTemplate = data.shop.shippingTemplate;
  const shippingEstimateZone = shippingTemplate?.zones?.find((zone) => zone.enabled) || shippingTemplate?.zones?.[0];
  const freeShippingApplies = Boolean(
    shippingEstimateZone?.freeShippingThreshold &&
    productSaleAmount >= shippingEstimateZone.freeShippingThreshold,
  );
  const estimatedShippingAmount = freeShippingApplies
    ? 0
    : Math.max(0, shippingEstimateZone?.firstFee ?? shippingTemplate?.firstFee ?? 0);
  const estimatedOrderTotal = productSaleAmount + estimatedShippingAmount;
  // The shipping template is the only shipping-cost source available during
  // listing. Treat the amount charged to the buyer as the estimated carrier
  // cost, so postage does not appear as product profit in the seller payout.
  const estimatedLogisticsCost = estimatedShippingAmount;
  const gatewayFeeRate =
    Math.max(0, Math.min(100, Number(estimatedGatewayFeeRate) || 0)) / 100;
  const estimatedGatewayFee = estimatedOrderTotal * gatewayFeeRate;
  const estimatedPlatformCommission = estimatedOrderTotal * 0.05;
  const estimatedSettlementAmount = Math.max(
    0,
    estimatedOrderTotal -
      estimatedGatewayFee -
      estimatedPlatformCommission -
      estimatedLogisticsCost,
  );
  const productDimensionValues = parseProductDimensions(form.dimensions);
  const updateProductDimension = (index: number, value: string) => {
    const nextValues = [...productDimensionValues];
    nextValues[index] = value;
    setForm({ ...form, dimensions: formatProductDimensions(nextValues) });
  };
  const [variantDrafts, setVariantDrafts] = useState<
    {
      id: number;
      name: string;
      values: { id: number; value: string; image?: string; imageAssetId?: string }[];
    }[]
  >([]);
  const [skuStocks, setSkuStocks] = useState<Record<string, string>>({});
  const [skuPrices, setSkuPrices] = useState<Record<string, string>>({});
  const [skuCodes, setSkuCodes] = useState<Record<string, string>>({});
  const [defaultSkuCode, setDefaultSkuCode] = useState("");
  const [skuStatuses, setSkuStatuses] = useState<
    Record<string, "active" | "disabled">
  >({});
  const [couponDraft, setCouponDraft] = useState({
    type: "full_reduction" as ShopPromotionType,
    threshold: "",
    value: "",
    startsAt: "",
    endsAt: "",
  });
  const [visitorCount, setVisitorCount] = useState(0);
  const [analyticsDays, setAnalyticsDays] = useState<1 | 7 | 30>(1);
  const [analytics, setAnalytics] = useState<{
    revenue: number;
    orders: number;
    visitors: number;
    conversionRate: number;
    pendingFulfillment: number;
    lowStock: number;
    refundRate: number;
  } | null>(null);
  const toastRef = useRef(toast);
  const sellerOrders = orders;
  const validSellerOrders = sellerOrders.filter(
    (order) => order.status !== "已取消",
  );
  const transactionAmount = validSellerOrders.reduce(
    (total, order) => total + order.amount,
    0,
  );
  useEffect(() => {
    let active = true;
    fetch(`${API_BASE}/api/analytics/shops/${analyticsShopId}`)
      .then((response) => (response.ok ? response.json() : { visitors: 0 }))
      .then((payload: { visitors: number }) => {
        if (active) setVisitorCount(payload.visitors || 0);
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, [analyticsShopId]);
  useEffect(() => {
    fetch(`${API_BASE}/api/analytics/seller?days=${analyticsDays}`, {
      credentials: "include",
    })
      .then((response) => (response.ok ? response.json() : Promise.reject()))
      .then((payload: { analytics: typeof analytics }) =>
        setAnalytics(payload.analytics),
      )
      .catch(() => undefined);
  }, [analyticsDays]);
  useEffect(() => {
    toastRef.current = toast;
  }, [toast]);
  useEffect(() => {
    messageSoundEnabledRef.current = messageSoundEnabled;
    window.localStorage.setItem(
      "seller-message-sound-enabled",
      String(messageSoundEnabled),
    );
  }, [messageSoundEnabled]);
  useEffect(() => {
    const unlock = () => void unlockNewBuyerMessageChime();
    document.addEventListener("pointerdown", unlock, { once: true });
    document.addEventListener("keydown", unlock, { once: true });
    return () => {
      document.removeEventListener("pointerdown", unlock);
      document.removeEventListener("keydown", unlock);
    };
  }, []);
  const playMessageSound = () => {
    if (!messageSoundEnabledRef.current) return;
    const now = Date.now();
    if (now - lastMessageSoundAtRef.current < 10000) return;
    lastMessageSoundAtRef.current = now;
    void playNewBuyerMessageChime();
  };
  const refreshMessageUnread = async () => {
    const response = await fetch(`${API_BASE}/api/messages/seller`, {
      credentials: "include",
    });
    const payload = (await response.json().catch(() => ({}))) as {
      conversations?: { unread: number }[];
    };
    if (response.ok)
      setMessageUnread(
        (payload.conversations || []).reduce(
          (total, item) => total + item.unread,
          0,
        ),
      );
  };
  useEffect(() => {
    void refreshMessageUnread().catch(() => undefined);
    const timer = window.setInterval(() => {
      void refreshMessageUnread().catch(() => undefined);
    }, 30000);
    return () => window.clearInterval(timer);
  }, []);
  useEffect(() => {
    if (typeof WebSocket === "undefined") return;
    let socket: WebSocket | null = null;
    let reconnectTimer: number | undefined;
    let disposed = false;
    const connect = () => {
      socket = new WebSocket(websocketUrl());
      socket.onmessage = (event) => {
        try {
          const payload = JSON.parse(String(event.data)) as {
            type?: string;
            audience?: string;
          };
          if (payload.type !== "message.new" || payload.audience !== "seller")
            return;
          void refreshMessageUnread().catch(() => undefined);
          playMessageSound();
          toastRef.current("收到新的买家消息");
        } catch {
          // Ignore malformed push events and keep the connection alive.
        }
      };
      socket.onclose = () => {
        if (!disposed) reconnectTimer = window.setTimeout(connect, 3000);
      };
    };
    connect();
    return () => {
      disposed = true;
      if (reconnectTimer !== undefined) window.clearTimeout(reconnectTimer);
      socket?.close();
    };
  }, []);
  const conversionRate = visitorCount
    ? `${((validSellerOrders.length / visitorCount) * 100).toFixed(1)}%`
    : "0.0%";
  const pendingFulfillmentCount = sellerOrders.filter(
    (order) => order.status === "待发货",
  ).length;
  const productSales = new Map<number, number>();
  for (const order of validSellerOrders) {
    for (const item of order.items) {
      if (
        data.products.find((product) => product.id === item.productId)
          ?.shopId !== 99
      )
        continue;
      productSales.set(
        item.productId,
        (productSales.get(item.productId) || 0) + item.quantity,
      );
    }
  }
  const hotProducts = sellerProducts
    .filter((product) => product.listed !== false)
    .map((product) => ({ product, sales: productSales.get(product.id) || 0 }))
    .sort(
      (left, right) =>
        right.sales - left.sales ||
        right.product.reviews - left.product.reviews,
    )
    .slice(0, 5);
  const inventoryWarnings = sellerProducts
    .filter((product) => product.listed !== false && lowStockCount(product) > 0)
    .sort((left, right) => left.stock - right.stock);
  const displayedRevenue = analytics?.revenue ?? transactionAmount;
  const displayedOrders = analytics?.orders ?? validSellerOrders.length;
  const displayedVisitors = analytics?.visitors ?? visitorCount;
  const displayedConversion = analytics
    ? `${analytics.conversionRate.toFixed(1)}%`
    : conversionRate;
  const displayedPending =
    analytics?.pendingFulfillment ?? pendingFulfillmentCount;
  const displayedLowStock = analytics?.lowStock ?? inventoryWarnings.length;
  const inventoryProduct =
    sellerProducts.find((product) => product.id === inventoryProductId) ||
    sellerProducts[0];
  const inventorySku =
    inventoryProduct?.skus?.find((sku) => sku.id === inventorySkuId) ||
    inventoryProduct?.skus?.find(
      (sku) => (sku.status ?? "active") === "active",
    );
  const inventorySearchResults = listedSellerProducts.filter((product) => {
    const keyword = inventorySearch.trim().toLowerCase();
    return (
      !keyword ||
      [
        product.title,
        product.code || "",
        product.catalogId || "",
        String(product.id),
      ].some((value) => value.toLowerCase().includes(keyword))
    );
  });
  const inventoryListRows = listedSellerProducts
    .flatMap((product) => (product.skus || []).map((sku) => ({ product, sku })))
    .filter(({ product, sku }) => {
      const keyword = inventorySearch.trim().toLowerCase();
      const spec = Object.entries(sku.optionValues)
        .map(([name, value]) => `${name}:${value}`)
        .join(" ");
      return (
        !keyword ||
        [
          product.title,
          product.code || "",
          product.catalogId || "",
          String(product.id),
          sku.code || "",
          spec,
        ].some((value) => value.toLowerCase().includes(keyword))
      );
    });
  const allVisibleInventorySelected =
    inventoryListRows.length > 0 &&
    inventoryListRows.every(({ sku }) =>
      inventorySelectedSkuIds.includes(sku.id),
    );
  const selectInventoryProduct = (product: Product) => {
    setInventoryProductId(product.id);
    setInventorySkuId(
      product.skus?.find((sku) => (sku.status ?? "active") === "active")?.id ||
        "",
    );
    setInventorySearch("");
    setInventorySearchOpen(false);
  };
  const selectInventorySku = (product: Product, sku: ProductSku) => {
    setInventoryProductId(product.id);
    setInventorySkuId(sku.id);
  };
  useEffect(() => {
    if (tab !== "inventory") return;
    const query = inventoryProduct?.catalogId
      ? `?productId=${encodeURIComponent(inventoryProduct.catalogId)}`
      : "";
    fetch(`${API_BASE}/api/seller/inventory/adjustments${query}`, {
      credentials: "include",
    })
      .then((response) => (response.ok ? response.json() : Promise.reject()))
      .then((payload: { adjustments: InventoryAdjustment[] }) =>
        setInventoryAdjustments(payload.adjustments),
      )
      .catch(() => setInventoryAdjustments([]));
  }, [tab, inventoryProduct?.catalogId]);
  const adjustInventory = async () => {
    if (!inventoryProduct?.catalogId || !inventorySku?.id || !inventoryQuantity)
      return toast("请选择作品、SKU 并填写调整数量");
    const quantity = Number(inventoryQuantity);
    if (!Number.isInteger(quantity) || quantity < 0)
      return toast("库存调整数量必须是非负整数");
    if (!inventoryReason.trim()) return toast("请填写库存调整原因");
    const response = await fetch(
      `${API_BASE}/api/seller/inventory/adjustments`,
      {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          productId: inventoryProduct.catalogId,
          skuId: inventorySku.id,
          type: inventoryAdjustmentType,
          quantity,
          reason: inventoryReason,
        }),
      },
    );
    const payload = (await response.json()) as {
      product?: Product;
      error?: string;
    };
    if (!response.ok || !payload.product)
      return toast(payload.error || "库存调整失败");
    setData((current) => ({
      ...current,
      products: current.products.map((product) =>
        product.catalogId === payload.product!.catalogId
          ? payload.product!
          : product,
      ),
    }));
    setInventoryQuantity("");
    setInventoryReason("");
    const history = await fetch(
      `${API_BASE}/api/seller/inventory/adjustments?productId=${encodeURIComponent(inventoryProduct.catalogId)}`,
      { credentials: "include" },
    );
    if (history.ok)
      setInventoryAdjustments(
        ((await history.json()) as { adjustments: InventoryAdjustment[] })
          .adjustments,
      );
    toast("库存已更新");
  };
  const setInventorySkuStatus = async (
    sku: ProductSku,
    status: "active" | "disabled",
  ) => {
    const response = await fetch(
      `${API_BASE}/api/seller/inventory/skus/${encodeURIComponent(sku.id)}/status`,
      {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status }),
      },
    );
    const payload = (await response.json()) as {
      product?: Product;
      error?: string;
    };
    if (!response.ok || !payload.product)
      return toast(payload.error || "SKU 状态更新失败");
    setData((current) => ({
      ...current,
      products: current.products.map((product) =>
        product.catalogId === payload.product!.catalogId
          ? payload.product!
          : product,
      ),
    }));
    toast(status === "active" ? "SKU 已启用" : "SKU 已停用");
  };
  const saveInventoryRow = async (product: Product, sku: ProductSku) => {
    const nextValue = inventoryRowValues[sku.id];
    if (nextValue === undefined) return;
    if (nextValue.trim() === "" || Number(nextValue) === sku.stock) {
      setInventoryRowValues((current) => {
        const next = { ...current };
        delete next[sku.id];
        return next;
      });
      return;
    }
    const quantity = Number(nextValue);
    if (!Number.isInteger(quantity) || quantity < 0) {
      toast("库存必须是非负整数");
      return;
    }
    if (!product.catalogId) return toast("作品尚未同步完成，无法保存库存");
    const response = await fetch(
      `${API_BASE}/api/seller/inventory/adjustments`,
      {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          productId: product.catalogId,
          skuId: sku.id,
          type: "set",
          quantity,
          reason: "直接修改库存",
        }),
      },
    );
    const payload = (await response.json().catch(() => ({}))) as {
      product?: Product;
      error?: string;
    };
    if (!response.ok || !payload.product)
      return toast(payload.error || "库存自动保存失败");
    setData((current) => ({
      ...current,
      products: current.products.map((item) =>
        item.catalogId === payload.product!.catalogId ? payload.product! : item,
      ),
    }));
    setInventoryRowValues((current) => {
      const next = { ...current };
      delete next[sku.id];
      return next;
    });
    if (inventoryProduct?.catalogId === product.catalogId) {
      const history = await fetch(
        `${API_BASE}/api/seller/inventory/adjustments?productId=${encodeURIComponent(product.catalogId)}`,
        { credentials: "include" },
      );
      if (history.ok)
        setInventoryAdjustments(
          ((await history.json()) as { adjustments: InventoryAdjustment[] })
            .adjustments,
        );
    }
    toast("库存已自动保存");
  };
  const saveInventoryList = async () => {
    const selectedRows = inventoryListRows.filter(({ sku }) =>
      inventorySelectedSkuIds.includes(sku.id),
    );
    if (!selectedRows.length) return toast("请先勾选需要修改的 SKU");
    if (!inventoryListReason.trim()) return toast("请填写本次盘点原因");
    const updates = selectedRows.flatMap(({ product, sku }) => {
      const nextValue = inventoryRowValues[sku.id];
      if (
        nextValue === undefined ||
        nextValue === "" ||
        Number(nextValue) === sku.stock
      )
        return [];
      const quantity = Number(nextValue);
      return Number.isInteger(quantity) && quantity >= 0 && product.catalogId
        ? [{ product, sku, quantity }]
        : [];
    });
    if (!updates.length)
      return toast("请在已选 SKU 的库存框中输入有效的新库存");
    const changedProducts: Product[] = [];
    const savedSkuIds: string[] = [];
    for (const item of updates) {
      const response = await fetch(
        `${API_BASE}/api/seller/inventory/adjustments`,
        {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            productId: item.product.catalogId,
            skuId: item.sku.id,
            type: "set",
            quantity: item.quantity,
            reason: inventoryListReason.trim(),
          }),
        },
      );
      const payload = (await response.json().catch(() => ({}))) as {
        product?: Product;
        error?: string;
      };
      if (!response.ok || !payload.product) {
        toast(payload.error || `${item.sku.code || "该 SKU"} 库存保存失败`);
        continue;
      }
      changedProducts.push(payload.product);
      savedSkuIds.push(item.sku.id);
    }
    if (!changedProducts.length) return;
    const productUpdates = new Map(
      changedProducts.map((product) => [product.catalogId, product]),
    );
    setData((current) => ({
      ...current,
      products: current.products.map(
        (product) => productUpdates.get(product.catalogId) || product,
      ),
    }));
    setInventoryRowValues((current) => {
      const next = { ...current };
      savedSkuIds.forEach((id) => delete next[id]);
      return next;
    });
    setInventorySelectedSkuIds((current) =>
      current.filter((id) => !savedSkuIds.includes(id)),
    );
    setInventoryListReason("");
    toast(`已保存 ${savedSkuIds.length} 个 SKU 的库存`);
  };
  const exportInventory = () => {
    const rows = [
      ["作品", "作品ID", "SKU", "规格", "售价", "可售库存", "状态", "预警阈值"],
    ];
    sellerProducts.forEach((product) =>
      (product.skus || []).forEach((sku) =>
        rows.push([
          product.title,
          product.catalogId || "",
          sku.code || "",
          Object.entries(sku.optionValues)
            .map(([name, value]) => `${name}:${value}`)
            .join(" / ") || "默认规格",
          String(sku.price ?? product.price),
          String(sku.stock),
          sku.status === "disabled" ? "停用" : "可售",
          String(product.lowStockThreshold ?? 3),
        ]),
      ),
    );
    const csv = `\uFEFF${rows.map((row) => row.map((value) => `"${value.replace(/"/g, '""')}"`).join(",")).join("\n")}`;
    const url = URL.createObjectURL(
      new Blob([csv], { type: "text/csv;charset=utf-8" }),
    );
    const link = document.createElement("a");
    link.href = url;
    link.download = "库存导出.csv";
    link.click();
    URL.revokeObjectURL(url);
  };
  const uploadMedia = async (data: string, mediaType: "image" | "video") => {
    const response = await fetch(`${API_BASE}/api/media`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ data, mediaType, visibility: "public" }),
    });
    const payload = (await response.json()) as { url?: string; error?: string };
    if (!response.ok || !payload.url)
      throw new Error(payload.error || "媒体上传失败");
    return payload.url.startsWith("/")
      ? `${API_BASE}${payload.url}`
      : payload.url;
  };
  const uploadProductImageDirect = async (
    image: Blob,
    onProgress?: (percent: number) => void,
    mediaType: "image" | "video" = "image",
  ): Promise<{ id: string; url: string }> => {
    const contentHash =
      typeof crypto !== "undefined" && crypto.subtle
        ? Array.from(
            new Uint8Array(
              await crypto.subtle.digest("SHA-256", await image.arrayBuffer()),
            ),
          )
            .map((value) => value.toString(16).padStart(2, "0"))
            .join("")
        : undefined;
    const ticketResponse = await fetch(
      `${API_BASE}/api/seller/media/direct-upload`,
      {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          mimeType: image.type,
          size: image.size,
          contentHash,
          mediaType,
        }),
      },
    );
    const ticket = (await ticketResponse.json().catch(() => ({}))) as {
      id?: string;
      uploadUrl?: string;
      previewUrl?: string;
      headers?: Record<string, string>;
      error?: string;
    };
    if (!ticketResponse.ok || !ticket.uploadUrl || !ticket.id) {
      const data = await imageBlobToDataUrl(image);
      const response = await fetch(`${API_BASE}/api/seller/media/upload`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mediaType, data }),
      });
      const local = (await response.json().catch(() => ({}))) as {
        id?: string;
        previewUrl?: string;
        error?: string;
      };
      if (!response.ok || !local.id || !local.previewUrl)
        throw new Error(local.error || ticket.error || "图片上传失败");
      onProgress?.(100);
      return {
        id: local.id,
        url: local.previewUrl.startsWith("/")
          ? `${API_BASE}${local.previewUrl}`
          : local.previewUrl,
      };
    }
    const uploadUrl = ticket.uploadUrl;
    const previewUrl = ticket.previewUrl || `/api/seller/media/assets/${ticket.id}/preview`;
    await new Promise<void>((resolve, reject) => {
      const request = new XMLHttpRequest();
      request.open("PUT", uploadUrl, true);
      Object.entries(ticket.headers || {}).forEach(([name, value]) =>
        request.setRequestHeader(name, value),
      );
      request.timeout = 120000;
      request.upload.onprogress = (event) => {
        if (event.lengthComputable)
          onProgress?.(
            Math.min(
              99,
              Math.max(3, Math.round((event.loaded / event.total) * 100)),
            ),
          );
      };
      request.onload = () =>
        request.status >= 200 && request.status < 300
          ? resolve()
          : reject(new Error("图片直传 COS 失败，请重试"));
      request.onerror = () =>
        reject(new Error("图片直传 COS 失败，请检查网络后重试"));
      request.ontimeout = () =>
        reject(new Error("图片上传超时，请检查网络后重试"));
      request.send(image);
    });
    const completeResponse = await fetch(`${API_BASE}/api/seller/media/complete`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ assetId: ticket.id }),
    });
    const complete = (await completeResponse.json().catch(() => ({}))) as {
      id?: string;
      previewUrl?: string;
      error?: string;
    };
    if (!completeResponse.ok || !complete.id || !complete.previewUrl)
      throw new Error(complete.error || "图片安全处理失败");
    onProgress?.(100);
    return {
      id: complete.id,
      url: complete.previewUrl.startsWith("/")
        ? `${API_BASE}${complete.previewUrl}`
        : complete.previewUrl || previewUrl,
    };
  };
  const imageBlobToDataUrl = (image: Blob) =>
    new Promise<string>((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result));
      reader.onerror = () => reject(new Error("无法读取图片"));
      reader.readAsDataURL(image);
    });
  const generateProductTitle = async (imageData: string) => {
    setIsGeneratingProductTitle(true);
    try {
      const response = await fetch(`${API_BASE}/api/generate-title`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ imageData }),
      });
      const payload = (await response.json().catch(() => ({}))) as {
        title?: string;
        titleZh?: string;
        error?: string;
      };
      const title = payload.title?.trim();
      if (!response.ok || !title)
        throw new Error(payload.error || "AI 标题生成失败，请稍后重试");
      setForm((value) =>
        value.title.trim() ? value : { ...value, title },
      );
      setGeneratedChineseTitle(payload.titleZh?.trim() || "");
      toast("已根据图片生成作品名称，可继续修改");
    } catch (error) {
      toast(
        error instanceof Error
          ? `图片上传成功，但${error.message}`
          : "图片上传成功，但 AI 标题生成失败",
      );
    } finally {
      setIsGeneratingProductTitle(false);
    }
  };
  const normalizeImageLegacy = (file: File) =>
    new Promise<string>((resolve, reject) => {
      if (!file.type.startsWith("image/"))
        return reject(new Error("请选择图片文件"));
      const reader = new FileReader();
      reader.onload = () => {
        const image = new Image();
        image.onload = () => {
          const canvas = document.createElement("canvas");
          canvas.width = 800;
          canvas.height = 800;
          const context = canvas.getContext("2d");
          if (!context) return reject(new Error("图片处理失败，请重试"));
          const scale = Math.max(800 / image.width, 800 / image.height);
          const width = image.width * scale;
          const height = image.height * scale;
          context.drawImage(
            image,
            (800 - width) / 2,
            (800 - height) / 2,
            width,
            height,
          );
          resolve(canvas.toDataURL("image/jpeg", 0.78));
        };
        image.onerror = () => reject(new Error("无法读取该图片"));
        image.src = String(reader.result);
      };
      reader.onerror = () => reject(new Error("无法读取该图片"));
      reader.readAsDataURL(file);
    });
  const normalizeImage = async (
    file: File,
    maxDimension = UPLOAD_IMAGE_MAX_DIMENSION,
  ) => {
    try {
      return await compressImageForUpload(file, maxDimension);
    } catch {
      return normalizeImageLegacy(file);
    }
  };
  const validateProductImage = (file: File) => {
    if (!PRODUCT_IMAGE_TYPES.has(file.type))
      return "图片仅支持 JPG、PNG 或 WebP 格式";
    if (file.size > MAX_PRODUCT_IMAGE_SIZE) return "单张图片不能超过 3MB";
    return "";
  };
  const chooseImages = async (files: FileList | null) => {
    const selected = Array.from(files || []);
    const remaining = 10 - form.images.length - pendingProductImageIds.length;
    if (!selected.length) return;
    if (remaining <= 0) return toast("最多只能上传 10 张图片");
    if (selected.length > remaining)
      return toast(`最多还能上传 ${remaining} 张图片`);
    const invalidMessage = selected.map(validateProductImage).find(Boolean);
    if (invalidMessage) return toast(invalidMessage);
    const pendingIds = selected.map(
      (_, index) => `uploading-${Date.now()}-${index}`,
    );
    setPendingProductImageIds((current) => [...current, ...pendingIds]);
    setPendingProductImageProgress((current) => ({
      ...current,
      ...Object.fromEntries(pendingIds.map((id) => [id, 0])),
    }));
    try {
      const uploads = await Promise.all(
        selected.map(async (file, index) => {
          const id = pendingIds[index];
          const normalizedImage = await compressImageBlobForUpload(file, 1600);
          setPendingProductImageProgress((current) => ({
            ...current,
            [id]: Math.max(2, current[id] || 0),
          }));
          const upload = await uploadProductImageDirect(normalizedImage, (percent) =>
            setPendingProductImageProgress((current) => ({
              ...current,
              [id]: percent,
            })),
          );
          return {
            ...upload,
            imageData:
              index === 0 && !form.title.trim()
                ? await imageBlobToDataUrl(normalizedImage)
                : undefined,
          };
        }),
      );
      setForm((value) => ({
        ...value,
        images: [...value.images, ...uploads.map((upload) => upload.url)],
        imageAssetIds: [...value.imageAssetIds, ...uploads.map((upload) => upload.id)],
      }));
      if (!form.title.trim() && uploads[0]?.imageData)
        void generateProductTitle(uploads[0].imageData);
    } catch (error) {
      toast(error instanceof Error ? error.message : "图片上传失败");
    } finally {
      setPendingProductImageIds((current) =>
        current.filter((id) => !pendingIds.includes(id)),
      );
      setPendingProductImageProgress((current) => {
        const next = { ...current };
        pendingIds.forEach((id) => delete next[id]);
        return next;
      });
    }
  };
  const chooseShopImage = async (field: "avatar" | "banner", file?: File) => {
    if (!file) return;
    try {
      const normalizedImage = await normalizeImage(file);
      const image = await uploadMedia(normalizedImage, "image");
      setData((current) => ({
        ...current,
        shop: { ...current.shop, [field]: image },
      }));
    } catch (error) {
      toast(error instanceof Error ? error.message : "图片上传失败");
    }
  };
  const chooseVideo = async (file?: File) => {
    if (!file) return;
    if (!PRODUCT_VIDEO_TYPES.has(file.type))
      return toast("视频仅支持 MP4、WebM 或 MOV 格式");
    if (file.size > MAX_PRODUCT_VIDEO_SIZE) return toast("视频不能超过 50MB");
    try {
      const upload = await uploadProductImageDirect(file, undefined, "video");
      setForm((value) => ({ ...value, video: upload.url, videoAssetId: upload.id }));
    } catch (error) {
      toast(error instanceof Error ? error.message : "视频上传失败");
    }
  };
  const chooseVariantImage = async (
    variantId: number,
    valueId: number,
    file?: File,
  ) => {
    if (!file) return;
    const validationError = validateProductImage(file);
    if (validationError) return toast(validationError);
    const uploadKey = `${variantId}:${valueId}`;
    setPendingVariantImageKeys((items) =>
      items.includes(uploadKey) ? items : [...items, uploadKey],
    );
    try {
      const normalizedImage = await compressImageBlobForUpload(file, 1600);
      const image = await uploadProductImageDirect(normalizedImage);
      setVariantImageLoadStates((states) => ({
        ...states,
        [uploadKey]: "loading",
      }));
      setVariantDrafts((items) =>
        items.map((variant) =>
          variant.id === variantId
            ? {
                ...variant,
                values: variant.values.map((value) =>
                  value.id === valueId
                    ? { ...value, image: image.url, imageAssetId: image.id }
                    : value,
                ),
              }
            : variant,
        ),
      );
    } catch (error) {
      toast(error instanceof Error ? error.message : "图片上传失败");
    } finally {
      setPendingVariantImageKeys((items) =>
        items.filter((key) => key !== uploadKey),
      );
    }
  };
  const moveImage = (from: number, to: number) => {
    if (from === to) return;
    setForm((value) => {
      const images = [...value.images];
      const [moved] = images.splice(from, 1);
      images.splice(to, 0, moved);
      const imageAssetIds = [...value.imageAssetIds];
      const [movedAssetId] = imageAssetIds.splice(from, 1);
      imageAssetIds.splice(to, 0, movedAssetId);
      return { ...value, images, imageAssetIds };
    });
  };
  const resetProductForm = () => {
    setForm({
      title: "",
      buyerTitle: "",
      buyerDescription: "",
      buyerMaterial: "",
      buyerSeoTags: [],
      price: "",
      category: "陶艺陶瓷",
      stock: "10",
      weightGrams: "",
      dimensions: "",
      lowStockThreshold: "3",
      description: "",
      material: "",
      craftsmanship: "",
      images: [],
      imageAssetIds: [],
      video: "",
      videoAssetId: "",
      seoTags: [],
      custom: false,
    });
    setSeoTagInput("");
    setGeneratedChineseTitle("");
    setVariantDrafts([]);
    setSkuStocks({});
    setSkuPrices({});
    setSkuCodes({});
    setDefaultSkuCode("");
    setSkuStatuses({});
    setPendingVariantImageKeys([]);
    setVariantImageLoadStates({});
    setEditingProductId(null);
    setEditingProductCatalogId(null);
    setEditingDraftId(null);
    setEditingDraftCatalogId(null);
  };
  const collectVariants = () =>
    variantDrafts
      .map((variant) => {
        const values = variant.values
          .map((item) => item.value.trim())
          .filter(Boolean);
        return {
          name: variant.name.trim(),
          values,
          valueImages: Object.fromEntries(
            variant.values
              .filter((item) => item.value.trim() && item.image)
              .map((item) => [item.value.trim(), item.image as string]),
          ),
          valueAssetIds: Object.fromEntries(
            variant.values
              .filter((item) => item.value.trim() && item.imageAssetId)
              .map((item) => [item.value.trim(), item.imageAssetId as string]),
          ),
        };
      })
      .filter((variant) => variant.name && variant.values.length);
  const variantStockCombinations = buildVariantCombinations(collectVariants());
  const hasCompleteVariants =
    variantDrafts.length > 0 &&
    variantDrafts.every(
      (variant) =>
        variant.name.trim() &&
        variant.values.length > 0 &&
        variant.values.every((value) => value.value.trim()),
    );
  const loadProductForm = (
    item: Pick<
      ProductDraft,
      | "title"
      | "price"
      | "category"
      | "stock"
      | "weightGrams"
      | "dimensions"
      | "lowStockThreshold"
      | "description"
      | "material"
      | "craftsmanship"
      | "buyerTitle"
      | "buyerDescription"
      | "buyerMaterial"
      | "buyerSeoTags"
      | "images"
      | "mediaAssetIds"
      | "imageAssetIds"
      | "video"
      | "videoAssetId"
      | "seoTags"
      | "custom"
      | "variants"
      | "skus"
    >,
  ) => {
    setForm({
      title: item.title,
      price: item.price,
      category: item.category,
      stock: item.stock,
      weightGrams: item.weightGrams || "",
      dimensions: item.dimensions || "",
      lowStockThreshold: item.lowStockThreshold || "3",
      description: item.description,
      material: item.material || "",
      craftsmanship: item.craftsmanship || "",
      buyerTitle: item.buyerTitle || "",
      buyerDescription: item.buyerDescription || "",
      buyerMaterial: item.buyerMaterial || "",
      buyerSeoTags: item.buyerSeoTags || [],
      images: item.images,
      imageAssetIds: item.imageAssetIds || item.mediaAssetIds?.slice(0, item.images.length) || [],
      video: item.video,
      videoAssetId: item.videoAssetId || "",
      seoTags: item.seoTags || [],
      custom: item.custom,
    });
    setSeoTagInput("");
    setVariantDrafts(
      item.variants.map((variant) => ({
        id: Date.now() + Math.random(),
        name: variant.name,
        values: variant.values.map((value) => ({
          id: Date.now() + Math.random(),
          value,
          image: variant.valueImages?.[value],
          imageAssetId: variant.valueAssetIds?.[value],
        })),
      })),
    );
    setSkuStocks(
      Object.fromEntries(
        (item.skus || []).map((sku) => [
          variantCombinationKey(sku.optionValues),
          String(sku.stock),
        ]),
      ),
    );
    setSkuPrices(
      Object.fromEntries(
        (item.skus || []).map((sku) => [
          variantCombinationKey(sku.optionValues),
          String(sku.price ?? item.price),
        ]),
      ),
    );
    setSkuCodes(
      Object.fromEntries(
        (item.skus || []).map((sku) => [
          variantCombinationKey(sku.optionValues),
          sku.code || "",
        ]),
      ),
    );
    setDefaultSkuCode(
      (item.skus || []).find(
        (sku) => Object.keys(sku.optionValues || {}).length === 0,
      )?.code || "",
    );
    setSkuStatuses(
      Object.fromEntries(
        (item.skus || []).map((sku) => [
          variantCombinationKey(sku.optionValues),
          sku.status ?? "active",
        ]),
      ),
    );
    setShowForm(true);
  };
  const saveDraft = async () => {
    const draft: ProductDraft = {
      id: editingDraftId || Date.now(),
      catalogId: editingDraftCatalogId || undefined,
      title: form.title || "未命名草稿",
      price: form.price,
      currency: "USD",
      category: form.category,
      stock: form.stock,
      weightGrams: form.weightGrams,
      dimensions: form.dimensions,
      lowStockThreshold: form.lowStockThreshold,
      description: form.description,
      material: form.material,
      craftsmanship: form.craftsmanship,
      buyerTitle: form.buyerTitle,
      buyerDescription: form.buyerDescription,
      buyerMaterial: form.buyerMaterial,
      buyerSeoTags: form.buyerSeoTags,
      images: form.images,
      mediaAssetIds: [...form.imageAssetIds, ...(form.videoAssetId ? [form.videoAssetId] : [])],
      imageAssetIds: form.imageAssetIds,
      video: form.video,
      videoAssetId: form.videoAssetId || undefined,
      seoTags: form.seoTags,
      custom: form.custom,
      variants: collectVariants(),
      skus: collectVariants().length
        ? variantStockCombinations.map((optionValues) => ({
            id: variantCombinationKey(optionValues),
            optionValues,
            stock:
              Number(
                skuStocks[variantCombinationKey(optionValues)] || form.stock,
              ) || 0,
            price:
              Number(
                skuPrices[variantCombinationKey(optionValues)] || form.price,
              ) || 0,
            code: skuCodes[variantCombinationKey(optionValues)] || "",
            status:
              skuStatuses[variantCombinationKey(optionValues)] || "active",
          }))
        : defaultSkuCode.trim()
          ? [{ id: "default", optionValues: {}, stock: Number(form.stock) || 0, price: Number(form.price) || 0, code: defaultSkuCode.trim(), status: "active" as const }]
          : [],
      updatedAt: "刚刚",
    };
    const response = await fetch(`${API_BASE}/api/seller/drafts`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ product: draft }),
    });
    const payload = (await response.json()) as {
      product?: Product;
      error?: string;
    };
    if (!response.ok || !payload.product)
      return toast(payload.error || "草稿保存失败");
    const savedDraft = {
      ...draft,
      id: payload.product.id,
      catalogId: payload.product.catalogId,
    };
    setData((current) => ({
      ...current,
      drafts: current.drafts.some((item) => item.id === draft.id)
        ? current.drafts.map((item) =>
            item.id === draft.id ? savedDraft : item,
          )
        : [savedDraft, ...current.drafts],
    }));
    setEditingDraftId(savedDraft.id);
    setEditingDraftCatalogId(savedDraft.catalogId || null);
    toast("草稿已保存");
  };
  const editProduct = (product: Product) => {
    setEditingProductId(product.id);
    setEditingProductCatalogId(product.catalogId || null);
    setEditingDraftId(null);
    setEditingDraftCatalogId(null);
    loadProductForm({
      title: product.title,
      price: String(product.price),
      category: product.category,
      stock: String(product.stock),
      weightGrams: product.weightGrams ? String(product.weightGrams) : "",
      dimensions: product.dimensions || "",
      lowStockThreshold: String(product.lowStockThreshold ?? 3),
      description: product.description,
      material: product.material || "",
      craftsmanship: product.craftsmanship || "",
      buyerTitle: product.buyerTitle || "",
      buyerDescription: product.buyerDescription || "",
      buyerMaterial: product.buyerMaterial || "",
      buyerSeoTags: product.buyerSeoTags || [],
      images: product.images || [product.image],
      mediaAssetIds: product.mediaAssetIds || [],
      imageAssetIds: product.imageAssetIds || [],
      video: product.video || "",
      videoAssetId: product.videoAssetId || "",
      seoTags: product.seoTags || [],
      custom: product.custom,
      variants: product.variants || [],
      skus: product.skus || [],
    });
  };
  const addSeoTag = () => {
    const tag = seoTagInput.trim().replace(/^#/, "");
    if (!tag) return;
    if (characterCount(tag) > 10) return toast("每个搜索标签最多 10 个字");
    if (form.seoTags.includes(tag)) return toast("该搜索标签已添加");
    if (form.seoTags.length >= 12) return toast("最多添加 12 个搜索标签");
    setForm((value) => ({ ...value, seoTags: [...value.seoTags, tag] }));
    setSeoTagInput("");
  };
  const addProduct = async () => {
    if (
      !form.title.trim() ||
      !form.price ||
      !form.description.trim() ||
      !form.material.trim() ||
      (!editingProductId && !form.craftsmanship.trim())
    )
      return toast("请填写作品名称、价格、描述、材质和制作工艺");
    if (productTitleCharacterUnits(form.title) > 250)
      return toast("作品名称最多 50 个汉字或 125 个英文字符，符号按 1 个字符计");
    if (!form.images.length) return toast("请至少上传 1 张作品图片");
    if (
      form.weightGrams &&
      (!Number.isInteger(Number(form.weightGrams)) ||
        Number(form.weightGrams) < 1 ||
        Number(form.weightGrams) > 100000)
    )
      return toast("重量请填写 1 至 100000 g 之间的整数");
    if (characterCount(form.dimensions) > 100)
      return toast("尺寸说明最多 100 个字");
    if (characterCount(form.craftsmanship) > 300)
      return toast("制作工艺最多 300 个字");
    const sensitiveWord = sensitiveContentWord(
      `${form.title}${form.description}${form.material}${form.craftsmanship}${form.seoTags.join("")}${form.buyerTitle}${form.buyerDescription}${form.buyerMaterial}${form.buyerSeoTags.join("")}`,
    );
    if (sensitiveWord)
      return toast(`内容审核未通过：包含敏感词“${sensitiveWord}”`);
    const incompleteVariant = variantDrafts.some(
      (variant) =>
        !variant.name.trim() ||
        variant.values.some((value) => !value.value.trim()),
    );
    if (incompleteVariant) return toast("每个规格都需要填写名称和规格值");
    const variants = collectVariants();
    if (variantStockCombinations.length > 100)
      return toast("规格组合不能超过 100 个");
    const skus = variants.length
      ? variantStockCombinations.map((optionValues) => {
          const key = variantCombinationKey(optionValues);
          return {
            id: key,
            optionValues,
            stock: Number(skuStocks[key] || form.stock) || 0,
            price: Number(skuPrices[key] || form.price) || 0,
            code: skuCodes[key] || "",
            status: skuStatuses[key] || "active",
          };
        })
      : defaultSkuCode.trim()
        ? [{ id: "default", optionValues: {}, stock: Number(form.stock) || 0, price: Number(form.price) || 0, code: defaultSkuCode.trim(), status: "active" as const }]
        : undefined;
    const p: Product = {
      id: Date.now(),
      catalogId: editingProductCatalogId || editingDraftCatalogId || undefined,
      title: form.title.trim(),
      price: Number(form.price),
      currency: "USD",
      category: form.category,
      stock: skus
        ? skus
            .filter((sku) => sku.status === "active")
            .reduce((total, sku) => total + sku.stock, 0)
        : Number(form.stock) || 1,
      weightGrams: form.weightGrams ? Number(form.weightGrams) : undefined,
      dimensions: form.dimensions.trim() || undefined,
      lowStockThreshold: Math.max(0, Number(form.lowStockThreshold) || 0),
      image:
        form.images[0] ||
        productImages[sellerProducts.length % productImages.length],
      images: form.images.length ? form.images : undefined,
      mediaAssetIds: [...form.imageAssetIds, ...(form.videoAssetId ? [form.videoAssetId] : [])],
      imageAssetIds: form.imageAssetIds,
      video: form.video || undefined,
      videoAssetId: form.videoAssetId || undefined,
      shopId: 99,
      shop: data.shop.name,
      rating: 5,
      reviews: 0,
      tags: ["新上架", "原创手作"],
      seoTags: form.seoTags,
      buyerTitle: form.buyerTitle.trim(),
      buyerDescription: form.buyerDescription.trim(),
      buyerMaterial: form.buyerMaterial.trim(),
      buyerSeoTags: form.buyerSeoTags,
      publishStatus: "published",
      reviewStatus: "approved",
      custom: form.custom,
      description: form.description,
      material: form.material.trim(),
      craftsmanship: form.craftsmanship.trim(),
      variants: variants.length ? variants : undefined,
      skus,
    };
    const response = await fetch(`${API_BASE}/api/seller/products`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ product: p, status: "published" }),
    });
    const payload = (await response.json()) as {
      product?: Product;
      error?: string;
    };
    if (!response.ok || !payload.product)
      return toast(payload.error || "作品保存失败");
    const savedProduct = payload.product;
    setData((v) => ({
      ...v,
      products: editingProductId
        ? v.products.map((product) =>
            product.id === editingProductId ? savedProduct : product,
          )
        : [savedProduct, ...v.products],
      drafts: editingDraftId
        ? v.drafts.filter((draft) => draft.id !== editingDraftId)
        : v.drafts,
    }));
    setShowForm(false);
    resetProductForm();
    toast(editingProductId ? "作品已更新" : "作品已发布");
  };
  const changeProductStatus = async (
    product: Product,
    status: "published" | "unlisted",
  ) => {
    if (!product.catalogId) return toast("作品尚未同步完成");
    const response = await fetch(
      `${API_BASE}/api/seller/products/${encodeURIComponent(product.catalogId)}/status`,
      {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status }),
      },
    );
    const payload = (await response.json()) as {
      product?: Product;
      error?: string;
    };
    if (!response.ok || !payload.product)
      return toast(payload.error || "作品状态更新失败");
    setData((current) => ({
      ...current,
      products: current.products.map((item) =>
        item.catalogId === payload.product!.catalogId ? payload.product! : item,
      ),
    }));
  };
  const removeProduct = async (product: Product) => {
    if (!product.catalogId) return toast("作品尚未同步完成");
    const response = await fetch(
      `${API_BASE}/api/seller/products/${encodeURIComponent(product.catalogId)}`,
      { method: "DELETE", credentials: "include" },
    );
    const payload = (await response.json()) as { error?: string };
    if (!response.ok) return toast(payload.error || "作品删除失败");
    setData((current) => ({
      ...current,
      products: current.products.filter(
        (item) => item.catalogId !== product.catalogId,
      ),
    }));
    toast("作品已彻底删除");
  };
  const appealProduct = async (product: Product) => {
    if (!product.catalogId) return toast("作品尚未同步完成");
    const content = window.prompt("请说明申诉理由");
    if (!content?.trim()) return;
    const response = await fetch(`${API_BASE}/api/governance/appeals`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        targetType: "product",
        targetId: product.catalogId,
        content: content.trim(),
      }),
    });
    const payload = (await response.json()) as { error?: string };
    toast(
      response.ok
        ? "申诉已提交，等待平台复审"
        : payload.error || "申诉提交失败",
    );
  };
  const applyBulkChanges = async () => {
    const products = listedSellerProducts.filter((product) =>
      selectedProductIds.includes(sellerProductSelectionId(product)),
    );
    const productIds = products
      .map((product) => product.catalogId)
      .filter(Boolean) as string[];
    if (productIds.length !== products.length)
      return toast("部分作品尚未同步完成");
    const response = await fetch(`${API_BASE}/api/seller/products/bulk`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        productIds,
        ...(bulkPrice ? { price: Number(bulkPrice) } : {}),
        ...(bulkStock ? { stock: Number(bulkStock) } : {}),
      }),
    });
    const payload = (await response.json()) as {
      products?: Product[];
      error?: string;
    };
    if (!response.ok || !payload.products)
      return toast(payload.error || "批量修改失败");
    const updates = new Map(
      payload.products.map((product) => [product.catalogId, product]),
    );
    setData((current) => ({
      ...current,
      products: current.products.map(
        (product) => updates.get(product.catalogId) || product,
      ),
    }));
    setBulkPrice("");
    setBulkStock("");
    toast("批量修改已保存");
  };
  const saveShop = async (shop: Shop = data.shop) => {
    const response = await fetch(`${API_BASE}/api/seller/shop`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ shop }),
    });
    const payload = (await response.json()) as { shop?: Shop; error?: string };
    if (!response.ok || !payload.shop)
      return toast(payload.error || "店铺设置保存失败");
    setData((current) => ({ ...current, shop: payload.shop! }));
    toast("店铺设置已保存");
  };
  const updateShippingTemplate = (
    updater: (template: ShippingTemplate) => ShippingTemplate,
  ) => {
    setData((current) => ({
      ...current,
      shop: {
        ...current.shop,
        shippingTemplate: updater(
          current.shop.shippingTemplate?.zones?.length
            ? current.shop.shippingTemplate
            : defaultInternationalShippingTemplate(),
        ),
      },
    }));
  };
  const storedBrandSite = data.shop.brandSite;
  const normalizedBrandSiteTemplate = normalizeBrandSiteTemplate(
    storedBrandSite?.template,
  );
  const brandSite: BrandSiteConfig = {
    ...defaultBrandSite,
    ...storedBrandSite,
    template: normalizedBrandSiteTemplate,
    sections: ensureBrandSiteSections(
      storedBrandSite?.sections,
      normalizedBrandSiteTemplate,
    ),
  };
  const returnPolicy = { ...DEFAULT_RETURN_POLICY, ...data.shop.returnPolicy };
  const updateBrandSite = (changes: Partial<BrandSiteConfig>) => {
    setData((current) => ({
      ...current,
      shop: {
        ...current.shop,
        brandSite: {
          ...defaultBrandSite,
          ...current.shop.brandSite,
          ...changes,
        },
      },
    }));
  };
  const updateBrandSiteSection = (
    id: BrandSiteSection["id"],
    changes: Partial<BrandSiteSection>,
  ) => {
    updateBrandSite({
      sections: brandSite.sections?.map((section) =>
        section.id === id ? { ...section, ...changes } : section,
      ),
    });
  };
  const moveBrandSiteSection = (
    id: BrandSiteSection["id"],
    direction: "up" | "down",
  ) => {
    const sections = [...(brandSite.sections || [])];
    const from = sections.findIndex((section) => section.id === id);
    const to = from + (direction === "up" ? -1 : 1);
    if (from < 0 || to < 0 || to >= sections.length) return;
    [sections[from], sections[to]] = [sections[to], sections[from]];
    updateBrandSite({ sections });
  };
  const updateReturnPolicy = (changes: Partial<ReturnPolicy>) => {
    setData((current) => ({
      ...current,
      shop: {
        ...current.shop,
        returnPolicy: {
          ...DEFAULT_RETURN_POLICY,
          ...current.shop.returnPolicy,
          ...changes,
        },
      },
    }));
  };
  const saveBrandSite = async (publish = false) => {
    const nextBrandSite: BrandSiteConfig = {
      ...brandSite,
      enabled: publish || brandSite.enabled,
      status: publish ? "published" : brandSite.status,
    };
    const nextShop = { ...data.shop, brandSite: nextBrandSite };
    setData((current) => ({ ...current, shop: nextShop }));
    await saveShop(nextShop);
  };
  const standaloneBrandEditor =
    new URLSearchParams(window.location.search).get("brandEditor") === "1";
  const openBrandSiteEditor = () => {
    const editorUrl = new URL(window.location.href);
    editorUrl.searchParams.set("view", "studio");
    editorUrl.searchParams.set("tab", "brand-site");
    editorUrl.searchParams.set("brandEditor", "1");
    // Open the standalone editor as a normal browser page, not a constrained popup.
    window.open(editorUrl.toString(), "_blank", "noopener");
  };
  const openPublicBrandSite = () => {
    const siteUrl = new URL(window.location.href);
    siteUrl.search = "";
    siteUrl.searchParams.set("site", "1");
    siteUrl.searchParams.set("shop", analyticsShopId);
    window.open(siteUrl.toString(), "_blank", "noopener");
  };
  if (standaloneBrandEditor)
    return (
      <Suspense fallback={<main className="app-loading" aria-busy="true"><span /></main>}>
        <LazyBrandSiteBuilder
          context={{
            brandSite,
            shop: data.shop,
            products: listedSellerProducts,
            onChange: updateBrandSite,
            onSectionChange: updateBrandSiteSection,
            onSectionMove: moveBrandSiteSection,
            onSave: saveBrandSite,
            apiBase: API_BASE,
            compressImageForUpload,
            brandSiteAdditionalSections,
            previewDependencies: {
              apiBase: API_BASE,
              normalizeBrandSiteTemplate,
              ensureBrandSiteSections,
              productListImageUrl,
              bundledCatalogImages,
              bundledMediaImages,
              buyerProductCopy,
              money,
            },
          }}
        />
      </Suspense>
    );
  return (
    <div className="studio" lang="zh-CN">
      <div className="studio-side">
        <div className="studio-shop-home">
          <a
            className="studio-platform-logo"
            href="/"
            aria-label="返回 Shouzuo Hub 平台首页"
            title="返回 Shouzuo Hub 平台首页"
          >
            <img
              className="studio-platform-logo-image"
              src={shouzuoWordmarkImage}
              alt="Shouzuo"
            />
          </a>
          <a
            className="studio-shop-preview"
            href={buyerPreviewUrl}
            target="_blank"
            rel="noopener noreferrer"
            title="在新标签中以买家视图预览店铺"
          >
            <span>店铺主页</span>
          </a>
        </div>
        <div className="studio-navigation">
          <div className="studio-quick-links">
            <button
              data-testid="seller-tab-overview"
            className={`studio-overview-link${tab === "overview" ? " active" : ""}`}
            onClick={() => openStudioTab("overview")}
          >
              <span>经营概览</span>
            </button>
          </div>
          {sellerNavigationGroups.map((group) => {
            const expanded = expandedSellerNavigationGroups[group.id] === true;
            return (
              <section className="studio-nav-group" key={group.id}>
                <button
                  type="button"
                  className={`studio-nav-group-toggle${expanded ? " open" : ""}`}
                  aria-expanded={expanded}
                  onClick={() =>
                    setExpandedSellerNavigationGroups((current) => ({
                      ...current,
                      [group.id]: !expanded,
                    }))
                  }
                >
                  <span>{group.label}</span>
                  <ChevronDown size={16} />
                </button>
                {expanded && (
                  <div className="studio-nav-group-items">
                    {group.items.map(({ id, label, Icon }) => (
                      <button
                        key={id}
                        data-testid={`seller-tab-${id}`}
                        className={tab === id ? "active" : ""}
                        onClick={() => openStudioTab(id)}
                      >
                        <Icon size={18} />
                        <span>{label}</span>
                        {id === "messages" && messageUnread > 0 && (
                          <i className="studio-message-unread">
                            {messageUnread > 99 ? "99+" : messageUnread}
                          </i>
                        )}
                      </button>
                    ))}
                  </div>
                )}
              </section>
            );
          })}
        </div>
        <button
          type="button"
          className={`studio-ai-assistant-entry${aiAssistantOpen ? " active" : ""}`}
          aria-expanded={aiAssistantOpen}
          onClick={() => setAiAssistantOpen((open) => !open)}
        >
          <MessageCircle size={18} />
          <span>AI运营助手</span>
        </button>
      </div>
      <div className="studio-main">
        {tab === "overview" && (
          <>
            <div className="studio-title">
              <div>
                <p className="eyebrow">你好，{data.shop.owner}</p>
                <h1>{studioText("今天也做点有意思的事", "Make something meaningful today")}</h1>
              </div>
              <button
                className="primary"
                onClick={() => {
                  openStudioTab("products");
                  setShowForm(true);
                }}
              >
                {studioText("发布作品", "Add product")}
              </button>
            </div>
            <div className="order-filters">
              <button
                className={analyticsDays === 1 ? "selected" : ""}
                onClick={() => setAnalyticsDays(1)}
              >
                今日
              </button>
              <button
                className={analyticsDays === 7 ? "selected" : ""}
                onClick={() => setAnalyticsDays(7)}
              >
                近 7 天
              </button>
              <button
                className={analyticsDays === 30 ? "selected" : ""}
                onClick={() => setAnalyticsDays(30)}
              >
                近 30 天
              </button>
            </div>
            <div className="metric-grid">
              <Metric
                label="成交额"
                value={money(displayedRevenue)}
                trend={`${displayedOrders} 笔有效订单`}
              />
              <Metric
                label="访客"
                value={displayedVisitors.toLocaleString()}
                trend={
                  analyticsDays === 1
                    ? "今日访问"
                    : `近 ${analyticsDays} 天访问`
                }
              />
              <Metric
                label="转化率"
                value={displayedConversion}
                trend="有效订单 / 访客"
              />
              <Metric
                label="待发货"
                value={String(displayedPending)}
                trend="需要优先处理"
              />
              <Metric
                label="库存预警"
                value={String(displayedLowStock)}
                trend="低库存作品"
              />
            </div>
            <div className="dashboard-grid">
              <section className="studio-panel dashboard-panel">
                <div className="panel-head">
                  <h3>热销作品</h3>
                  <button
                    className="text-link"
                    onClick={() => openStudioTab("products")}
                  >
                    管理作品
                  </button>
                </div>
                {hotProducts.length ? (
                  <div className="dashboard-product-list">
                    {hotProducts.map(({ product, sales }, index) => (
                      <button
                        key={product.id}
                        onClick={() => onOpen(product.id)}
                      >
                        <em>{index + 1}</em>
                        <img src={productListImageUrl(product.image, 160)} alt="" />
                        <span>
                          <b>{product.title}</b>
                          <small>
                            {sales} 件成交 · {money(product.price)}
                          </small>
                        </span>
                      </button>
                    ))}
                  </div>
                ) : (
                  <p>发布作品后，成交数据会在这里汇总。</p>
                )}
              </section>
              <section className="studio-panel dashboard-panel dashboard-fulfillment">
                <div className="panel-head">
                  <h3>待发货</h3>
                  <button
                    className="text-link"
                    onClick={() => openStudioTab("orders")}
                  >
                    查看订单
                  </button>
                </div>
                <b className="dashboard-emphasis">
                  {pendingFulfillmentCount} 笔
                </b>
                <p>
                  {pendingFulfillmentCount
                    ? "请及时确认库存并录入物流单号。"
                    : "当前没有等待发货的订单。"}
                </p>
              </section>
              <section className="studio-panel dashboard-panel">
                <div className="panel-head">
                  <h3>库存预警</h3>
                  <button
                    className="text-link"
                    onClick={() => openStudioTab("products")}
                  >
                    调整库存
                  </button>
                </div>
                {inventoryWarnings.length ? (
                  <div className="dashboard-stock-list">
                    {inventoryWarnings.slice(0, 4).map((product) => (
                      <button
                        key={product.id}
                        onClick={() => onOpen(product.id)}
                      >
                        <span>{product.title}</span>
                        <b>{product.stock} 件</b>
                      </button>
                    ))}
                  </div>
                ) : (
                  <p>所有上架作品的库存都在安全范围内。</p>
                )}
              </section>
            </div>
          </>
        )}
        {tab === "products" && (
          <>
            <div className="studio-title">
              <div>
                <h1>{studioText("我的作品", "Products")}</h1>
                <p>{studioText("管理你的原创作品与库存", "Manage your listings and stock")}</p>
              </div>
              {(showForm || displayedSellerProducts.length > 0) && (
                <div className="studio-actions">
                  <button
                    className="primary"
                    onClick={() => {
                      if (showForm) {
                        setShowForm(false);
                        resetProductForm();
                      } else {
                        resetProductForm();
                        setShowForm(true);
                      }
                    }}
                  >
                    {showForm ? "取消编辑" : "发布作品"}
                  </button>
                </div>
              )}
            </div>
            {showForm && (
              <Suspense fallback={<section className="studio-panel publish-form" aria-busy="true"><span className="app-loading"><span /></span></section>}>
                <LazySellerProductEditor context={{
                  editingProductId,
                  form,
                  setForm,
                  isGeneratingProductTitle,
                  generatedChineseTitle,
                  chooseVideo,
                  productImageLoadStates,
                  setProductImageLoadStates,
                  dragOverImageIndex,
                  draggedImageIndex,
                  setDraggedImageIndex,
                  setDragOverImageIndex,
                  moveImage,
                  pendingProductImageIds,
                  pendingProductImageProgress,
                  chooseImages,
                  settlementEstimatorExpanded,
                  setSettlementEstimatorExpanded,
                  estimatedGatewayFeeRate,
                  setEstimatedGatewayFeeRate,
                  shippingTemplate,
                  freeShippingApplies,
                  productSaleAmount,
                  estimatedShippingAmount,
                  estimatedOrderTotal,
                  gatewayFeeRate,
                  estimatedGatewayFee,
                  estimatedPlatformCommission,
                  estimatedLogisticsCost,
                  estimatedSettlementAmount,
                  productDimensionValues,
                  updateProductDimension,
                  variantDrafts,
                  setVariantDrafts,
                  skuStocks,
                  setSkuStocks,
                  skuPrices,
                  setSkuPrices,
                  skuCodes,
                  setSkuCodes,
                  defaultSkuCode,
                  setDefaultSkuCode,
                  skuStatuses,
                  setSkuStatuses,
                  seoTagInput,
                  setSeoTagInput,
                  addSeoTag,
                  pendingVariantImageKeys,
                  variantImageLoadStates,
                  setVariantImageLoadStates,
                  chooseVariantImage,
                  variantStockCombinations,
                  variantCombinationKey,
                  saveDraft,
                  addProduct,
                  money,
                  productListImageUrl,
                  variantImageBusy: pendingVariantImageKeys.length > 0,
                  hasCompleteVariants,
                }} />
              </Suspense>
            )}

            {!showForm && (
              <Suspense fallback={<section className="studio-panel" aria-busy="true"><span className="app-loading"><span /></span></section>}>
                <LazySellerProductList context={{
                  showForm,
                  productListMode,
                  setProductListMode,
                  listedSellerProducts,
                  recycledSellerProducts,
                  selectedProductIds,
                  setSelectedProductIds,
                  sellerProductSelectionId,
                  bulkPrice,
                  setBulkPrice,
                  bulkStock,
                  setBulkStock,
                  applyBulkChanges,
                  displayedSellerProducts,
                  onOpen,
                  productListImageUrl,
                  lowStockCount,
                  money,
                  editProduct,
                  changeProductStatus,
                  removeProduct,
                  appealProduct,
                  data,
                  setEditingProductId,
                  setEditingProductCatalogId,
                  setEditingDraftId,
                  setEditingDraftCatalogId,
                  loadProductForm,
                }} />
              </Suspense>
            )}

          </>
        )}
        {tab === "inventory" && (
          <Suspense fallback={<main className="app-loading" aria-busy="true"><span /></main>}>
            <LazySellerInventoryPage context={{
              studioText,
              exportInventory,
              inventoryProduct,
              inventoryListRows,
              inventorySearch,
              setInventorySearch,
              inventoryListReason,
              setInventoryListReason,
              inventorySelectedSkuIds,
              setInventorySelectedSkuIds,
              saveInventoryList,
              allVisibleInventorySelected,
              productListImageUrl,
              selectInventorySku,
              inventoryRowValues,
              setInventoryRowValues,
              saveInventoryRow,
              money,
              inventorySku,
              setInventorySkuId,
              setInventorySkuStatus,
              inventoryAdjustmentType,
              setInventoryAdjustmentType,
              inventoryQuantity,
              setInventoryQuantity,
              inventoryReason,
              setInventoryReason,
              adjustInventory,
              inventoryAdjustments,
              openStudioTab,
              setShowForm,
            }} />
          </Suspense>
        )}
        {tab === "orders" && (
          <Suspense fallback={<main className="app-loading" aria-busy="true"><span /></main>}>
            <LazySellerFulfillmentPage context={{
              studioText,
              sellerOrders,
              data,
              money,
              StatusPill,
              setShipmentOrder,
              shipmentOrder,
              onShip,
              onShipping,
              setShipmentEventOrder,
              shipmentEventOrder,
              onAddShipmentEvent,
              afterSales,
              setAfterSaleDecision,
              afterSaleDecision,
              onReceiveReturn,
              onResolveAfterSale,
              productListImageUrl,
            }} />
          </Suspense>
        )}
        {tab === "messages" && (
          <Suspense fallback={null}>
            <LazyMessagesPage
              role="seller"
              embedded
              apiBase={API_BASE}
              compressImageForUpload={compressImageForUpload}
              productListImageUrl={productListImageUrl}
              onUnreadChange={setMessageUnread}
              messageSoundEnabled={messageSoundEnabled}
              onMessageSoundEnabledChange={setMessageSoundEnabled}
              onTestMessageSound={() => void playNewBuyerMessageChime()}
            />
          </Suspense>
        )}
        {tab === "reviews" && (
          <Suspense fallback={<main className="app-loading" aria-busy="true"><span /></main>}>
            <LazySellerReviewsPage context={{
              studioText,
              reviews,
              replyingReviewId,
              setReplyingReviewId,
              reviewReply,
              setReviewReply,
              onReplyReview,
            }} />
          </Suspense>
        )}
        {tab === "brand-site" && (
          <Suspense fallback={<main className="app-loading" aria-busy="true"><span /></main>}>
            <LazySellerBrandSitePage context={{
              studioText,
              brandSite,
              openPublicBrandSite,
              openBrandSiteEditor,
              updateBrandSite,
              saveBrandSite,
            }} />
          </Suspense>
        )}
        {tab === "finance" && (
          <Suspense fallback={<main className="app-loading" aria-busy="true"><span /></main>}>
            <LazyFinanceCenter toast={toast} apiBase={API_BASE} />
          </Suspense>
        )}
        {tab === "shipping" && (
          <Suspense fallback={<main className="app-loading" aria-busy="true"><span /></main>}>
            <LazySellerShippingPage context={{
              studioText,
              data,
              setData,
              shippingTemplate,
              sellerShippingText,
              updateShippingTemplate,
              defaultInternationalShippingTemplate,
              listedSellerProducts,
              productListImageUrl,
              saveShop,
            }} />
          </Suspense>
        )}
        {tab === "service" && (
          <>
            <div className="studio-title">
              <div>
                <h1>{studioText("资料与认证", "Verification")}</h1>
                <p>{studioText("填写店铺经营资料并提交认证材料", "Provide business information and verification documents")}</p>
              </div>
            </div>
            <Suspense fallback={<main className="app-loading" aria-busy="true"><span /></main>}>
              <LazySellerServiceManagement
                shopId={analyticsShopId}
                section="verification"
                apiBase={API_BASE}
                imageCompressor={compressImageForUpload}
                operatingCategories={SELLER_OPERATING_CATEGORIES}
              />
            </Suspense>
          </>
        )}
        {tab === "members" && (
          <>
            <div className="studio-title">
              <div>
                <h1>{studioText("成员与权限", "Team & access")}</h1>
                <p>{studioText("管理店铺协作者、岗位权限与操作审计", "Manage collaborators, permissions, and audit history")}</p>
              </div>
            </div>
            <Suspense fallback={<main className="app-loading" aria-busy="true"><span /></main>}>
              <LazySellerServiceManagement
                shopId={analyticsShopId}
                section="members"
                apiBase={API_BASE}
                imageCompressor={compressImageForUpload}
                operatingCategories={SELLER_OPERATING_CATEGORIES}
              />
            </Suspense>
          </>
        )}
        {tab === "support" && (
          <>
            <div className="studio-title">
              <div>
                <h1>{studioText("客服工单", "Support tickets")}</h1>
                <p>{studioText("集中处理买家咨询与售后工单", "Handle buyer enquiries and after-sales tickets")}</p>
              </div>
            </div>
            <Suspense fallback={<main className="app-loading" aria-busy="true"><span /></main>}>
              <LazySellerServiceManagement
                shopId={analyticsShopId}
                section="support"
                apiBase={API_BASE}
                imageCompressor={compressImageForUpload}
                operatingCategories={SELLER_OPERATING_CATEGORIES}
              />
            </Suspense>
          </>
        )}
        {tab === "advisor" && (
          <Suspense fallback={<main className="app-loading" aria-busy="true"><span /></main>}>
            <LazyDataAdvisor onOpenTab={openStudioTab} />
          </Suspense>
        )}
        {tab === "activities" && (
          <>
            <div className="studio-title">
              <div>
                <h1>{studioText("活动报名", "Campaigns")}</h1>
                <p>{studioText("报名平台活动并提交活动作品配额", "Join platform campaigns and submit product allocations")}</p>
              </div>
            </div>
            <Suspense fallback={<main className="app-loading" aria-busy="true"><span /></main>}>
              <LazySellerActivityOperations
                shopId={analyticsShopId}
                apiBase={API_BASE}
              />
            </Suspense>
          </>
        )}
        {tab === "promotions" && (
          <Suspense fallback={<main className="app-loading" aria-busy="true"><span /></main>}>
            <LazySellerPromotionsPage context={{
              studioText,
              couponDraft,
              setCouponDraft,
              data,
              setData,
              saveShop,
              toast,
              money,
            }} />
          </Suspense>
        )}
        {tab === "settings" && (
          <Suspense fallback={<main className="app-loading" aria-busy="true"><span /></main>}>
            <LazySellerSettingsPage context={{
              studioText,
              data,
              setData,
              chooseShopImage,
              returnPolicy,
              updateReturnPolicy,
              saveShop,
            }} />
          </Suspense>
        )}
      </div>
      {aiAssistantOpen && (
        <Suspense fallback={null}>
          <LazySellerAiAssistant
            floating
            onClose={() => setAiAssistantOpen(false)}
          />
        </Suspense>
      )}
    </div>
  );
}

function Metric({
  label,
  value,
  trend,
}: {
  label: string;
  value: string;
  trend: string;
}) {
  return (
    <div className="metric">
      <span>{label}</span>
      <b>{value}</b>
      <small>{trend}</small>
    </div>
  );
}
function Empty({
  title,
  text,
  action,
  onAction,
  actionAsLink = false,
}: {
  title: string;
  text: string;
  action?: string;
  onAction?: () => void;
  actionAsLink?: boolean;
}) {
  return (
    <div className="empty">
      <ShoppingBag size={32} />
      <h2>{title}</h2>
      <p>{text}</p>
      {action && onAction && (
        <button
          className={actionAsLink ? "empty-action-link" : "primary"}
          onClick={onAction}
        >
          {action}
          {actionAsLink && <ChevronRight size={16} />}
        </button>
      )}
    </div>
  );
}
