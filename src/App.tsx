import { useEffect, useRef, useState, type FormEvent, type MouseEvent } from "react";
import {
  ArrowLeft,
  Check,
  ChevronRight,
  CreditCard,
  Heart,
  LogOut,
  MapPin,
  ImagePlus,
  Menu,
  MessageCircle,
  Minus,
  Package,
  Plus,
  Search,
  Settings2,
  ShoppingBag,
  SlidersHorizontal,
  Star,
  Store,
  Truck,
  UserRound,
  Video,
  X,
  type LucideIcon,
} from "lucide-react";
import ceramicCupImage from "./images/ceramic-cup.jpg";
import moonstoneEarringsImage from "./images/moonstone-earrings.jpg";
import woolTableRunnerImage from "./images/wool-table-runner.jpg";
import springCardImage from "./images/spring-card.jpg";
import vintageVaseImage from "./images/vintage-vase.jpg";
import shopBannerImage from "./images/shop-banner.jpg";
import shopAvatarImage from "./images/shop-avatar.jpg";

type Category = "陶艺" | "首饰" | "织物" | "纸艺" | "家居" | "复古";
type OrderStatus =
  | "待付款"
  | "待发货"
  | "运输中"
  | "待收货"
  | "已完成"
  | "已取消";
type ProductVariant = {
  name: string;
  values: string[];
  valueImages?: Record<string, string>;
};
type ProductSku = {
  id: string;
  optionValues: Record<string, string>;
  stock: number;
  code?: string;
  price?: number;
  status?: "active" | "disabled";
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
type Product = {
  id: number;
  title: string;
  category: Category;
  price: number;
  oldPrice?: number;
  image: string;
  images?: string[];
  video?: string;
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
  lowStockThreshold?: number;
  tags: string[];
  custom: boolean;
  description: string;
  material: string;
  variants?: ProductVariant[];
  skus?: ProductSku[];
};
type ProductDraft = {
  id: number;
  catalogId?: string;
  title: string;
  price: string;
  category: Category;
  stock: string;
  lowStockThreshold?: string;
  description: string;
  images: string[];
  video: string;
  seoTags?: string[];
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
  isDefault: boolean;
};
type CheckoutQuote = {
  itemAmount: number;
  shippingAmount: number;
  discountAmount: number;
  amount: number;
  shops?: { shopId: string; shop: string; itemAmount: number; shippingAmount: number; discountAmount: number; amount: number }[];
};
type Shipment = {
  carrier: string;
  trackingNo: string;
  trackingPhoneLast4?: string;
  events: { time: string; label: string; detail: string }[];
};
type ShipmentDraft = {
  carrier: string;
  trackingNo: string;
};

export function shipmentTrackingLink(carrier: string, trackingNo: string) {
  const number = encodeURIComponent(trackingNo.trim());
  const normalizedCarrier = carrier.trim().toLowerCase();
  const official = (url: string, requiresPhoneLast4 = false) => ({ url, official: true, requiresPhoneLast4 });

  if (normalizedCarrier.includes("dhl"))
    return official(`https://www.dhl.com/global-en/home/tracking.html?tracking-id=${number}`);
  if (normalizedCarrier.includes("fedex"))
    return official(`https://www.fedex.com/fedextrack/?trknbr=${number}`);
  if (normalizedCarrier === "ups" || normalizedCarrier.includes("ups "))
    return official(`https://www.ups.com/track?tracknum=${number}`);
  if (normalizedCarrier.includes("usps"))
    return official(`https://tools.usps.com/go/TrackConfirmAction?tLabels=${number}`);
  if (normalizedCarrier.includes("aramex"))
    return official(`https://www.aramex.com/track/shipments?ShipmentNumber=${number}`);
  if (normalizedCarrier.includes("tnt"))
    return official(`https://www.tnt.com/express/en_us/site/shipping-tools/tracking.html?searchType=con&cons=${number}`);
  if (normalizedCarrier.includes("顺丰") || normalizedCarrier.includes("sf express"))
    return official(`https://www.sf-express.com/cn/sc/dynamic_function/waybill/#search/bill-number/${number}`, true);
  if (normalizedCarrier.includes("japan post") || normalizedCarrier.includes("日本邮便"))
    return official(`https://trackings.post.japanpost.jp/services/srv/search/?requestNo1=${number}`);
  if (normalizedCarrier.includes("australia post"))
    return official(`https://auspost.com.au/mypost/track/#/details/${number}`);

  return { url: `https://www.17track.net/en/track#nums=${number}`, official: false, requiresPhoneLast4: false };
}
type PaymentMethod = "alipay" | "card";
type Payment = {
  method: PaymentMethod;
  status: "pending" | "succeeded" | "cancelled" | "failed";
  reference?: string;
  paidAt?: string;
};
type Order = {
  id: string;
  orderId?: string;
  shopId?: string;
  buyerUserId?: string;
  items: CartItem[];
  status: OrderStatus;
  createdAt: string;
  amount: number;
  itemAmount?: number;
  shippingAmount?: number;
  discountAmount?: number;
  shipment?: Shipment;
  payment?: Payment;
  reviewed?: boolean;
};
type ShopMessage = {
  id: string | number;
  shopId: string | number;
  shop?: string;
  buyerUserId?: string;
  buyer?: string;
  sender: "buyer" | "seller";
  type?: "text" | "image" | "order";
  content: string;
  attachmentUrl?: string;
  order?: { id: string; orderNo?: string; status?: string; amount?: number; title?: string; image?: string } | null;
  read?: boolean;
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
type AfterSaleRequest = {
  id: string | number;
  orderId: string;
  type: "退款" | "退货退款";
  reason: string;
  status: "待处理" | "待退货" | "待收货" | "已同意" | "已拒绝" | "已退款";
  createdAt: string;
  amount?: number;
  sellerResponse?: string;
  evidence?: string[];
  returnAddress?: string;
  returnShipment?: { carrier: string; trackingNo: string; shippedAt: string };
  timeline?: { time: string; label: string; detail: string }[];
};
type AfterSaleDraft = {
  type: "refund" | "return_refund";
  amount: number;
  reason: string;
  evidence: string[];
};
type ReviewDraft = {
  rating: number;
  content: string;
  images: string[];
};
type ReturnShipmentDraft = {
  carrier: string;
  trackingNo: string;
};
type ProductReview = {
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
  shippingTemplate?: {
    name: string;
    firstFee: number;
    additionalFee: number;
    freeShippingThreshold?: number;
  };
  coupons?: { id: number; threshold: number; discount: number }[];
  featuredProductIds?: number[];
};
type FollowedShop = {
  id: string | number;
  name: string;
};
type AppData = {
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
type SellerRegistrationProfile = {
  realName: string;
  identityNumber: string;
  address: string;
  payoutProvider: "lianlian";
  operatingCategories: string[];
};
const SELLER_OPERATING_CATEGORIES = [
  "布艺缝纫", "黏土&塑形", "滴胶&树脂", "编织", "木质&木艺", "皮具", "首饰", "陶艺陶瓷",
  "刺绣", "花艺干花", "香薰蜡烛 & 香氛", "古风国风", "绘画肌理", "纸品文创", "宠物专属",
  "苔藓微景观", "羊毛毡", "皂类", "非遗",
] as const;
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
  | "studio";
const buyerRestorableViews: MarketplaceView[] = [
  "home", "discover", "cart", "checkout", "orders", "favorites", "coupons", "following",
  "messages", "notifications", "profile", "security",
];
const sellerRestorableViews: MarketplaceView[] = ["home", "shop", "studio", "profile", "security", "notifications"];

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
const categories: { name: Category; image: string; caption: string }[] = [
  { name: "陶艺", image: productImages[0], caption: "泥土与火" },
  { name: "首饰", image: productImages[1], caption: "独一无二" },
  { name: "织物", image: productImages[2], caption: "柔软手感" },
  { name: "纸艺", image: productImages[3], caption: "纸上灵感" },
  { name: "家居", image: productImages[4], caption: "日常器物" },
  { name: "复古", image: productImages[5], caption: "旧日珍藏" },
];

function createInitialData(account: Account): AppData {
  return {
    ...initialData,
    role: account.role === "seller" ? "seller" : "buyer",
    shop: {
      ...demoShop,
      owner: account.name,
      name: `${account.name}的手作店`,
    },
  };
}

// In production the frontend and API are served from the same origin through
// the reverse proxy. Keep the API base relative by default; an absolute
// VITE_API_BASE can still be supplied for a separately hosted API.
const API_BASE = (import.meta as ImportMeta & { env?: { VITE_API_BASE?: string } }).env?.VITE_API_BASE ?? "";

function mergeProducts(current: Product[], incoming: Product[]) {
  return [
    ...current.filter((product) => !incoming.some((remote) => remote.id === product.id)),
    ...incoming.map((product) => ({
      ...product,
      image: bundledCatalogImages[product.catalogId || ""] || product.image,
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
    if (isGuest) return () => {
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
        const payload = (await response.json()) as { state: Partial<AppData> | null };
        if (!active) return;
        setData({ ...initial, ...payload.state, role: account.role === "seller" ? "seller" : "buyer" });
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
      .then((payload: { messages: ShopMessage[] }) => setData((current) => ({ ...current, messages: payload.messages })))
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
  return [data, setData] as const;
}

function money(value: number) {
  return `¥${value.toFixed(2)}`;
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
const PRODUCT_IMAGE_TYPES = new Set(["image/jpeg", "image/png", "image/webp"]);
const PRODUCT_VIDEO_TYPES = new Set(["video/mp4", "video/webm", "video/quicktime"]);
const MAX_PRODUCT_IMAGE_SIZE = 10 * 1024 * 1024;
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
        variant.values.map((value) => ({ ...combination, [variant.name]: value })),
      ),
    [{}],
  );
}
function lowStockCount(product: Product, threshold = product.lowStockThreshold ?? 3) {
  if (product.skus?.length)
    return product.skus.filter((sku) => (sku.status ?? "active") === "active" && sku.stock > 0 && sku.stock <= threshold)
      .length;
  return product.stock > 0 && product.stock <= threshold ? 1 : 0;
}
function StatusPill({ status, className = "" }: { status: OrderStatus; className?: string }) {
  return <span className={`status status-${status} ${className}`.trim()}>{status}</span>;
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

const guestAccount: Account = {
  id: "guest",
  name: "游客",
  password: "",
  role: "buyer",
};

const isAuthRoute = () => new URLSearchParams(window.location.search).get("auth") === "login";

const setAuthRoute = (visible: boolean) => {
  const url = new URL(window.location.href);
  if (visible) url.searchParams.set("auth", "login");
  else url.searchParams.delete("auth");
  const nextUrl = `${url.pathname}${url.search}${url.hash}`;
  if (nextUrl !== `${window.location.pathname}${window.location.search}${window.location.hash}`)
    window.history.replaceState(null, "", nextUrl);
};

export default function App() {
  const [account, setAccount] = useState<Account | null>(null);
  const [showAuth, setShowAuth] = useState(isAuthRoute);
  const [sessionReady, setSessionReady] = useState(false);
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
  const openAuth = () => {
    setShowAuth(true);
    setAuthRoute(true);
  };

  const login = async (identifier: string, password: string) => {
    try {
      const response = await fetch(`${API_BASE}/api/auth/login`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ identifier, password }),
      });
      const payload = (await response.json()) as { account?: Account; error?: string };
      if (!response.ok || !payload.account) return payload.error || "账号或密码不正确";
      setAccount(payload.account);
      closeAuth();
      return "";
    } catch {
      return "服务连接失败，请稍后重试";
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
    sellerProfile?: SellerRegistrationProfile,
  ) => {
    const normalizedEmail = email.trim().toLowerCase();
    if (!name.trim() || !password || (role === "seller" ? !phone : (!phone && !normalizedEmail)))
      return role === "seller" ? "店主注册请填写昵称、手机号和密码" : "请填写昵称、密码和至少一种登录账号";
    if (phone && !/^1\d{10}$/.test(phone)) return "请输入正确的 11 位手机号";
    if (normalizedEmail && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(normalizedEmail))
      return "请输入正确的邮箱地址";
    if (password.length < 8) return "密码至少需要 8 位";
    if (password !== confirmPassword) return "两次输入的密码不一致";
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
          sellerProfile,
        }),
      });
      const payload = (await response.json()) as { account?: Account; error?: string };
      if (!response.ok || !payload.account) return payload.error || "注册失败";
      setAccount(payload.account);
      closeAuth();
      return "";
    } catch {
      return "服务连接失败，请稍后重试";
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
      setAccount(null);
    }
  };
  const updateAccount = (changes: Partial<Account>) => {
    setAccount((current) => (current ? { ...current, ...changes } : current));
  };

  if (!sessionReady)
    return <main className="app-loading" aria-busy="true" aria-label="正在恢复登录状态"><span /></main>;
  if (!account && showAuth)
    return (
      <AuthScreen
        onLogin={login}
        onRegister={register}
        onBack={closeAuth}
      />
    );
  return (
    account?.role === "admin" ? (
      <AdminConsole account={account} onLogout={logout} />
    ) : (
    <Marketplace
      key={account?.id || guestAccount.id}
      account={account || guestAccount}
      isGuest={!account}
      onAuth={openAuth}
      onLogout={logout}
      onAccountUpdated={updateAccount}
      onAccountDeleted={() => setAccount(null)}
    />
    )
  );
}

export function AuthScreen({
  onLogin,
  onRegister,
  onBack,
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
    sellerProfile?: SellerRegistrationProfile,
  ) => Promise<string>;
  onBack: () => void;
}) {
  const [mode, setMode] = useState<"login" | "register">("login");
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
  const [role, setRole] = useState<Account["role"]>("buyer");
  const [sellerStep, setSellerStep] = useState<1 | 2>(1);
  const [realName, setRealName] = useState("");
  const [identityNumber, setIdentityNumber] = useState("");
  const [address, setAddress] = useState("");
  const [operatingCategories, setOperatingCategories] = useState<string[]>([]);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const requestPhoneCode = async () => {
    setError("");
    if (!/^1\d{10}$/.test(phone)) {
      setError("请先填写正确的 11 位手机号");
      return;
    }
    setSendingPhoneCode(true);
    try {
      const response = await fetch(`${API_BASE}/api/auth/request-verification`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ destination: phone, purpose: "contact_verify", registration: true }) });
      const payload = await response.json().catch(() => ({})) as { error?: string; developmentCode?: string };
      if (!response.ok) {
        setError(payload.error || "验证码发送失败");
        return;
      }
      setPhoneCodeSent(true);
      setPhoneDevelopmentCode(payload.developmentCode || "");
    } catch {
      setError("服务连接失败，请稍后重试");
    } finally {
      setSendingPhoneCode(false);
    }
  };
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (mode === "register" && password !== confirmPassword) {
      setError("两次输入的密码不一致");
      return;
    }
    if (mode === "register" && role === "seller" && sellerStep === 1) {
      if (!name.trim() || !/^1\d{10}$/.test(phone) || password.length < 8 || !phoneVerificationCode.trim()) {
        setError("请完整填写昵称、手机号、验证码和至少 8 位密码");
        return;
      }
      if (email.trim() && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) {
        setError("请输入正确的邮箱地址");
        return;
      }
      setError("");
      setSellerStep(2);
      return;
    }
    if (mode === "register" && role === "seller" && (!realName.trim() || !identityNumber.trim() || !address.trim() || !operatingCategories.length)) {
      setError("请完整填写经营资料并选择经营类目");
      return;
    }
    setSubmitting(true);
    const message = await (
      mode === "login"
        ? onLogin(identifier.trim(), password)
        : onRegister(name, phone, email, password, confirmPassword, phoneVerificationCode, role, role === "seller" ? { realName, identityNumber, address, payoutProvider: "lianlian", operatingCategories } : undefined));
    setError(message);
    setSubmitting(false);
  };
  return (
    <main className="auth-page">
      <section className="auth-art">
        <div className="auth-brand">
          手作<span>集</span>
        </div>
        <div>
          <p>HANDMADE, ORIGINAL, YOURS</p>
          <h1>让每一件认真做的东西，被认真看见。</h1>
          <span>发现独立创作者，也开始分享你的作品。</span>
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
              登录
            </button>
            <button
              data-testid="auth-register-tab"
              className={mode === "register" ? "active" : ""}
              onClick={() => {
                setMode("register");
                setError("");
              }}
            >
              注册
            </button>
          </div>
          <h2>{mode === "login" ? "欢迎回来" : "创建你的账户"}</h2>
          <p>
            {mode === "login"
              ? "登录后继续你的手作之旅。"
              : "注册后即可浏览、购买或开启个人店铺。"}
          </p>
          <form data-testid="auth-form" onSubmit={submit}>
            {mode === "register" && sellerStep === 2 ? (
              <div className="seller-registration-step">
                <label>真实姓名<input data-testid="seller-real-name" value={realName} onChange={(event) => setRealName(event.target.value)} placeholder="填写身份证上的姓名" required /></label>
                <label>身份证号<input data-testid="seller-identity-number" value={identityNumber} onChange={(event) => setIdentityNumber(event.target.value)} placeholder="填写身份证号码" required /></label>
                <label>经营地址<input data-testid="seller-address" value={address} onChange={(event) => setAddress(event.target.value)} placeholder="填写常用经营地址" required /></label>
                <div className="seller-payout-handoff"><b>连连收款账户</b><span>注册完成后，在“结算与资金”中绑定连连账户。银行卡信息将由连连安全页面采集，平台不保存完整卡号。</span></div>
                <label className="seller-category-select">经营类目
                  <select data-testid="seller-category-select" value={operatingCategories[0] || ""} onChange={(event) => setOperatingCategories(event.target.value ? [event.target.value] : [])} required>
                    <option value="">请选择经营类目</option>
                    {SELLER_OPERATING_CATEGORIES.map((category) => <option key={category} value={category}>{category}</option>)}
                  </select>
                </label>
                <div className="auth-step-actions"><button data-testid="seller-registration-back" className="secondary" type="button" onClick={() => { setError(""); setSellerStep(1); }}>上一步</button><button data-testid="auth-submit" className="primary" type="submit" disabled={submitting}>提交注册</button></div>
              </div>
            ) : mode === "register" && (
              <label>
                昵称
                <input
                  data-testid="auth-name"
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  placeholder="怎么称呼你"
                  autoComplete="name"
                />
              </label>
            )}
            {mode === "login" ? (
              <label>
                手机号或邮箱
                <input
                  data-testid="auth-identifier"
                  value={identifier}
                  onChange={(event) => setIdentifier(event.target.value)}
                  placeholder="输入手机号或邮箱"
                  autoComplete="username"
                />
              </label>
            ) : sellerStep === 1 ? (
              <>
                <label>
                  手机号{role === "seller" ? "" : "（可选）"}
                  <input
                    data-testid="auth-phone"
                    value={phone}
                    onChange={(event) =>
                      (() => {
                        setPhone(event.target.value.replace(/\D/g, "").slice(0, 11));
                        setPhoneVerificationCode("");
                        setPhoneCodeSent(false);
                        setPhoneDevelopmentCode("");
                      })()
                    }
                    placeholder="11 位手机号"
                    inputMode="numeric"
                    autoComplete="tel"
                    required={role === "seller"}
                  />
                </label>
                {role === "seller" && <div className="seller-phone-verification">
                  <div className="seller-phone-code-row"><input data-testid="auth-phone-code" value={phoneVerificationCode} onChange={(event) => setPhoneVerificationCode(event.target.value.replace(/\D/g, "").slice(0, 6))} placeholder="请输入 6 位验证码" inputMode="numeric" maxLength={6} required /><button data-testid="auth-phone-code-request" className="secondary" type="button" onClick={() => void requestPhoneCode()} disabled={sendingPhoneCode}>{phoneCodeSent ? "重新获取" : "获取验证码"}</button></div>
                  {phoneDevelopmentCode && <small className="auth-hint">开发环境验证码：{phoneDevelopmentCode}</small>}
                </div>}
                <label>
                  邮箱（可选）
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
                  {role === "seller" ? "店主注册需填写手机号，邮箱可选。" : "手机号和邮箱至少填写一项，填写后均可登录。"}
                </small>
              </>
            ) : null}
            {(mode === "login" || sellerStep === 1) && <label>
              密码
              <input
                data-testid="auth-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder={mode === "register" ? "至少 8 位" : "输入密码"}
                type="password"
                autoComplete={
                  mode === "login" ? "current-password" : "new-password"
                }
              />
            </label>}
            {mode === "register" && sellerStep === 1 && (
              <label>
                确认密码
                <input
                  data-testid="auth-confirm-password"
                  value={confirmPassword}
                  onChange={(event) => setConfirmPassword(event.target.value)}
                  placeholder="再次输入密码"
                  type="password"
                  autoComplete="new-password"
                />
              </label>
            )}
            {mode === "register" && sellerStep === 1 && (
              <div className="role-options">
                <span>注册身份</span>
                <label className={role === "buyer" ? "selected" : ""}>
                  <input
                    type="radio"
                    checked={role === "buyer"}
                    onChange={() => { setRole("buyer"); setSellerStep(1); }}
                  />
                  买家<small>发现和购买手作</small>
                </label>
                <label className={role === "seller" ? "selected" : ""}>
                  <input
                    type="radio"
                    checked={role === "seller"}
                    onChange={() => { setRole("seller"); setSellerStep(1); }}
                  />
                  店主<small>管理作品和订单</small>
                </label>
              </div>
            )}
            {error && <div className="auth-error" role="alert">{error}</div>}
            {!(mode === "register" && role === "seller" && sellerStep === 2) && <button data-testid="auth-submit" className="primary full" type="submit" disabled={submitting}>
              {mode === "login" ? "登录" : role === "seller" ? "下一步" : "注册并进入手作集"}
            </button>}
          </form>
          <button className="auth-back" onClick={onBack}>
            返回首页
          </button>
        </div>
      </section>
    </main>
  );
}

function AdminConsole({ account, onLogout }: { account: Account; onLogout: () => void }) {
  const [reports, setReports] = useState<{
    id: string; targetType: string; targetId: string; reason: string; detail: string; status: string; reporter: string; createdAt: string;
  }[]>([]);
  const [products, setProducts] = useState<{
    id: string; title: string; shop: string; status: string; moderationStatus: string; reason?: string;
  }[]>([]);
  const [notice, setNotice] = useState("");
  const [stepUp, setStepUp] = useState<{ action: (ticket: string) => Promise<void>; developmentCode?: string } | null>(null);
  const [stepUpCode, setStepUpCode] = useState("");
  const [stepUpError, setStepUpError] = useState("");
  const [analyticsDays, setAnalyticsDays] = useState<7 | 30 | 90>(30);
  const [analytics, setAnalytics] = useState<{ days: number; revenue: number; orders: number; activeShops: number; pendingReports: number; pendingAppeals: number; appealHours: number; orderStatuses: Record<string, number>; activeCampaigns: number; daily: { date: string; revenue: number; orders: number }[]; categories: { name: string; sales: number; revenue: number }[]; topShops: { name: string; orders: number; revenue: number }[]; campaignPerformance: CampaignSummary[]; funnel: { visitors: number; views: number; addCarts: number; checkouts: number; paidBuyers: number; viewToCartRate: number; cartToCheckoutRate: number; checkoutToPaidRate: number; cartDropOff: number; checkoutDropOff: number; paymentDropOff: number }; channels: { channel: string; visitors: number; addCarts: number; checkouts: number; paidOrders: number; revenue: number; visitorToCartRate: number; checkoutToPaidRate: number }[]; repeatCustomers: number; repeatRate: number; quality: { paidOrders: number; averageOrderValue: number; averageItemValue: number; refundOrders: number; refundAmount: number; refundRate: number; afterSaleRate: number; fulfillmentHours: number }; customers: { new: number; repeat: number; repeatOrders: number; repeatRevenue: number; repeatRate: number }; productPerformance: { id: string; title: string; views: number; sales: number; revenue: number; conversionRate: number }[] } | null>(null);
  const [announcements, setAnnouncements] = useState<{ id: string; title: string; content: string; audience: string; status: string; publishedAt?: string }[]>([]);
  type CampaignSummary = { id: string; name: string; type: "coupon" | "full_reduction"; status: string; rule: { threshold?: number; discount?: number }; budget: number | null; budgetRemaining: number | null; totalUsageLimit: number | null; perUserUsageLimit: number; reserved: number; redemptions: number; reversed: number; spent: number; attributedRevenue: number; attributedOrders: number; redemptionRate: number; averageOrderValue: number; roi: number | null; usageRemaining: number | null };
  const [campaigns, setCampaigns] = useState<CampaignSummary[]>([]);
  const [governanceTasks, setGovernanceTasks] = useState<{ id: string; type: string; targetId: string; status: string; assigneeId?: string; assignee?: string; createdAt: string }[]>([]);
  const [governanceAdmins, setGovernanceAdmins] = useState<{ id: string; name: string }[]>([]);
  const [governanceRules, setGovernanceRules] = useState<{ id: string; name: string; keyword: string; action: "manual_review" | "reject"; enabled: boolean }[]>([]);
  const [enforcementTemplates, setEnforcementTemplates] = useState<{ id: string; name: string; targetType: "product" | "shop" | "user"; action: string; reason: string; enabled: boolean }[]>([]);
  const [selectedProducts, setSelectedProducts] = useState<string[]>([]);
  const [ruleDraft, setRuleDraft] = useState({ name: "", keyword: "", action: "manual_review" as "manual_review" | "reject" });
  const [templateDraft, setTemplateDraft] = useState({ name: "", targetType: "product" as "product" | "shop" | "user", action: "unlist_product", reason: "" });
  const [announcementDraft, setAnnouncementDraft] = useState({ title: "", content: "", audience: "all", status: "draft" });
  const [campaignDraft, setCampaignDraft] = useState({ name: "", type: "coupon" as "coupon" | "full_reduction", status: "draft", threshold: "", discount: "", budget: "", totalUsageLimit: "", perUserUsageLimit: "1" });
  const [editingCampaignId, setEditingCampaignId] = useState<string | null>(null);
  const load = async () => {
    const [reportsResponse, productsResponse, analyticsResponse, operationsResponse, governanceResponse] = await Promise.all([
      fetch(`${API_BASE}/api/admin/reports`, { credentials: "include" }),
      fetch(`${API_BASE}/api/admin/moderation/products`, { credentials: "include" }),
      fetch(`${API_BASE}/api/analytics/admin?days=${analyticsDays}`, { credentials: "include" }),
      fetch(`${API_BASE}/api/admin/operations`, { credentials: "include" }),
      fetch(`${API_BASE}/api/admin/governance`, { credentials: "include" }),
    ]);
    if (reportsResponse.ok) setReports(((await reportsResponse.json()) as { reports: typeof reports }).reports);
    if (productsResponse.ok) setProducts(((await productsResponse.json()) as { products: typeof products }).products);
    if (analyticsResponse.ok) setAnalytics(((await analyticsResponse.json()) as { analytics: NonNullable<typeof analytics> }).analytics);
    if (operationsResponse.ok) {
      const operations = (await operationsResponse.json()) as { announcements: typeof announcements; campaigns: typeof campaigns };
      setAnnouncements(operations.announcements); setCampaigns(operations.campaigns);
    }
    if (governanceResponse.ok) {
      const governance = (await governanceResponse.json()) as { tasks: typeof governanceTasks; admins: typeof governanceAdmins; rules: typeof governanceRules; templates: typeof enforcementTemplates };
      setGovernanceTasks(governance.tasks); setGovernanceAdmins(governance.admins); setGovernanceRules(governance.rules); setEnforcementTemplates(governance.templates);
    }
  };
  useEffect(() => { void load(); }, [analyticsDays]);
  const beginStepUp = async (action: (ticket: string) => Promise<void>) => {
    setStepUpError("");
    const response = await fetch(`${API_BASE}/api/auth/request-admin-step-up`, {
      method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: "{}",
    });
    const result = await response.json().catch(() => ({})) as { error?: string; developmentCode?: string };
    if (!response.ok) return setNotice(result.error || "无法发送二次验证码");
    setStepUpCode("");
    setStepUp({ action, developmentCode: result.developmentCode });
  };
  const confirmStepUp = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!stepUp) return;
    setStepUpError("");
    const response = await fetch(`${API_BASE}/api/auth/confirm-admin-step-up`, {
      method: "POST", credentials: "include", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code: stepUpCode }),
    });
    const result = await response.json().catch(() => ({})) as { error?: string; ticket?: string };
    if (!response.ok || !result.ticket) return setStepUpError(result.error || "验证失败，请重试");
    await stepUp.action(result.ticket);
    setStepUp(null);
    setStepUpCode("");
  };
  const resolveReport = (id: string, decision: "resolved" | "dismissed") => beginStepUp(async (ticket) => {
    const response = await fetch(`${API_BASE}/api/admin/reports/${encodeURIComponent(id)}`, {
      method: "POST", credentials: "include", headers: { "Content-Type": "application/json", "X-Admin-Step-Up": ticket },
      body: JSON.stringify({ decision, unlistProduct: decision === "resolved" }),
    });
    if (!response.ok) return setNotice("举报处理失败");
    setNotice("举报已处理");
    void load();
  });
  const moderate = (id: string, decision: "approved" | "rejected") => beginStepUp(async (ticket) => {
    const response = await fetch(`${API_BASE}/api/admin/moderation/products/${encodeURIComponent(id)}`, {
      method: "POST", credentials: "include", headers: { "Content-Type": "application/json", "X-Admin-Step-Up": ticket },
      body: JSON.stringify({ decision, reason: decision === "rejected" ? "管理员审核未通过" : "" }),
    });
    if (!response.ok) return setNotice("审核处理失败");
    setNotice(decision === "approved" ? "作品已通过审核" : "作品已下架");
    void load();
  });
  const bulkModerate = (decision: "approved" | "rejected") => beginStepUp(async (ticket) => {
    const response = await fetch(`${API_BASE}/api/admin/moderation/products/bulk`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json", "X-Admin-Step-Up": ticket }, body: JSON.stringify({ productIds: selectedProducts, decision, reason: decision === "rejected" ? "批量审核未通过" : "" }) });
    const payload = await response.json().catch(() => ({})) as { error?: string; count?: number };
    if (!response.ok) return setNotice(payload.error || "批量审核失败");
    setSelectedProducts([]); setNotice(`已批量${decision === "approved" ? "通过" : "驳回"} ${payload.count || 0} 件作品`); void load();
  });
  const saveRule = () => beginStepUp(async (ticket) => {
    const response = await fetch(`${API_BASE}/api/admin/governance/rules`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json", "X-Admin-Step-Up": ticket }, body: JSON.stringify(ruleDraft) });
    const payload = await response.json().catch(() => ({})) as { error?: string };
    if (!response.ok) return setNotice(payload.error || "审核规则保存失败");
    setRuleDraft({ name: "", keyword: "", action: "manual_review" }); setNotice("审核规则已保存"); void load();
  });
  const saveTemplate = () => beginStepUp(async (ticket) => {
    const response = await fetch(`${API_BASE}/api/admin/governance/templates`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json", "X-Admin-Step-Up": ticket }, body: JSON.stringify(templateDraft) });
    const payload = await response.json().catch(() => ({})) as { error?: string };
    if (!response.ok) return setNotice(payload.error || "处罚模板保存失败");
    setTemplateDraft({ name: "", targetType: "product", action: "unlist_product", reason: "" }); setNotice("处罚模板已保存"); void load();
  });
  const assignTask = (taskId: string, assigneeId: string) => beginStepUp(async (ticket) => {
    const response = await fetch(`${API_BASE}/api/admin/governance/tasks/${encodeURIComponent(taskId)}/assign`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json", "X-Admin-Step-Up": ticket }, body: JSON.stringify({ assigneeId: assigneeId || null }) });
    if (!response.ok) return setNotice("任务分派失败");
    setNotice("治理任务已分派"); void load();
  });
  const exportGovernance = async () => {
    const response = await fetch(`${API_BASE}/api/admin/governance/export`, { credentials: "include" });
    const payload = await response.json().catch(() => ({})) as { tasks?: { type: string; targetId: string; status: string; assignee: string; createdAt: string; completedAt: string }[]; enforcements?: { action: string; targetType: string; targetId: string; reason: string; status: string; createdAt: string }[] };
    if (!response.ok) return setNotice("治理数据导出失败");
    const rows = [["类型", "对象", "状态", "处理人", "创建时间", "完成时间"], ...(payload.tasks || []).map((item) => [item.type, item.targetId, item.status, item.assignee, item.createdAt, item.completedAt]), ["处罚动作", "对象类型", "对象", "原因", "状态", "创建时间"], ...(payload.enforcements || []).map((item) => [item.action, item.targetType, item.targetId, item.reason, item.status, item.createdAt])];
    const csv = `\uFEFF${rows.map((row) => row.map((value) => `"${String(value).replace(/"/g, '""')}"`).join(",")).join("\n")}`;
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" })); const link = document.createElement("a"); link.href = url; link.download = "平台治理数据.csv"; link.click(); URL.revokeObjectURL(url);
  };
  const saveAnnouncement = () => beginStepUp(async (ticket) => {
    const response = await fetch(`${API_BASE}/api/admin/announcements`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json", "X-Admin-Step-Up": ticket }, body: JSON.stringify(announcementDraft) });
    const payload = await response.json().catch(() => ({})) as { error?: string };
    if (!response.ok) return setNotice(payload.error || "公告保存失败");
    setAnnouncementDraft({ title: "", content: "", audience: "all", status: "draft" }); setNotice("公告已保存"); void load();
  });
  const saveCampaign = () => beginStepUp(async (ticket) => {
    const response = await fetch(`${API_BASE}/api/admin/campaigns`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json", "X-Admin-Step-Up": ticket }, body: JSON.stringify({ id: editingCampaignId || undefined, name: campaignDraft.name, type: campaignDraft.type, status: campaignDraft.status, budget: Number(campaignDraft.budget), totalUsageLimit: Number(campaignDraft.totalUsageLimit), perUserUsageLimit: Number(campaignDraft.perUserUsageLimit), rule: { threshold: Number(campaignDraft.threshold), discount: Number(campaignDraft.discount) } }) });
    const payload = await response.json().catch(() => ({})) as { error?: string };
    if (!response.ok) return setNotice(payload.error || "活动保存失败");
    setCampaignDraft({ name: "", type: "coupon", status: "draft", threshold: "", discount: "", budget: "", totalUsageLimit: "", perUserUsageLimit: "1" }); setEditingCampaignId(null); setNotice("活动已保存"); void load();
  });
  const editCampaign = (item: CampaignSummary) => { setEditingCampaignId(item.id); setCampaignDraft({ name: item.name, type: item.type, status: item.status, threshold: String(item.rule.threshold || 0), discount: String(item.rule.discount || ""), budget: item.budget === null ? "" : String(item.budget), totalUsageLimit: item.totalUsageLimit === null ? "" : String(item.totalUsageLimit), perUserUsageLimit: String(item.perUserUsageLimit) }); window.scrollTo({ top: 0, behavior: "smooth" }); };
  const endCampaign = (id: string) => beginStepUp(async (ticket) => { const response = await fetch(`${API_BASE}/api/admin/campaigns/${encodeURIComponent(id)}/end`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json", "X-Admin-Step-Up": ticket }, body: "{}" }); if (!response.ok) return setNotice("活动结束失败"); setNotice("活动已结束，新的领取与抵扣已停止"); void load(); });
  const exportAnalytics = async () => {
    const response = await fetch(`${API_BASE}/api/analytics/admin/export?days=${analyticsDays}`, { credentials: "include" });
    const payload = await response.json().catch(() => ({})) as { days?: number; sections?: { name: string; headers: string[]; rows: (string | number)[][] }[]; error?: string };
    if (!response.ok || !payload.sections) return setNotice(payload.error || "运营报表导出失败");
    const rows = payload.sections.flatMap((section) => [[section.name], section.headers, ...section.rows, []] as (string | number)[][]);
    const csv = `\uFEFF${rows.map((row) => row.map((value) => `"${String(value).replace(/"/g, '""')}"`).join(",")).join("\n")}`;
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = `平台运营深度报表-${payload.days || analyticsDays}天.csv`;
    link.click();
    URL.revokeObjectURL(url);
  };
  return (
    <main className="container page section">
      <header className="page-title">
        <div><h1>平台治理</h1><p>{account.name}，审核作品与处理用户举报</p></div>
        <button className="secondary" onClick={onLogout}>退出</button>
      </header>
      {notice && <p className="auth-error">{notice}</p>}
      {stepUp && <div className="admin-step-up-backdrop" role="presentation">
        <form className="admin-step-up-dialog" onSubmit={(event) => void confirmStepUp(event)}>
          <h2>管理员二次验证</h2>
          <p>已向您的管理员验证联系方式发送 6 位验证码。</p>
          {stepUp.developmentCode && <p className="admin-step-up-code">开发环境验证码：{stepUp.developmentCode}</p>}
          <input aria-label="二次验证码" inputMode="numeric" maxLength={6} pattern="[0-9]{6}" value={stepUpCode} onChange={(event) => setStepUpCode(event.target.value.replace(/\D/g, ""))} placeholder="请输入 6 位验证码" autoFocus required />
          {stepUpError && <p className="auth-error">{stepUpError}</p>}
          <div className="admin-step-up-actions"><button type="button" className="secondary" onClick={() => setStepUp(null)}>取消</button><button className="primary" type="submit">验证并继续</button></div>
        </form>
      </div>}
      <div className="analytics-toolbar"><div><button className={analyticsDays === 7 ? "active" : ""} onClick={() => setAnalyticsDays(7)}>近 7 天</button><button className={analyticsDays === 30 ? "active" : ""} onClick={() => setAnalyticsDays(30)}>近 30 天</button><button className={analyticsDays === 90 ? "active" : ""} onClick={() => setAnalyticsDays(90)}>近 90 天</button></div><button className="secondary" onClick={() => void exportAnalytics()} disabled={!analytics}>导出深度报表</button></div>
      {analytics && <div className="metric-grid"><Metric label="近 30 天交易额" value={money(analytics.revenue)} trend={`${analytics.orders} 笔订单`} /><Metric label="活跃店铺" value={String(analytics.activeShops)} trend="有成交店铺" /><Metric label="治理待办" value={String(analytics.pendingReports + analytics.pendingAppeals)} trend={`${analytics.pendingReports} 举报 · ${analytics.pendingAppeals} 申诉`} /><Metric label="申诉处理时效" value={`${analytics.appealHours} 小时`} trend={`待付款 ${analytics.orderStatuses.pending_payment || 0} · 待发货 ${analytics.orderStatuses.pending_fulfillment || 0}`} /></div>}
      {analytics && <section className="admin-analytics-grid"><div className="studio-panel analytics-trend"><div className="panel-head"><h2>交易趋势</h2><span>{analytics.activeCampaigns} 个活动生效中</span></div><div className="trend-bars">{analytics.daily.map((item) => <div key={item.date} title={`${item.date} · ${money(item.revenue)} · ${item.orders} 单`}><i style={{ height: `${Math.max(4, analytics.daily.reduce((max, value) => Math.max(max, value.revenue), 0) ? item.revenue / analytics.daily.reduce((max, value) => Math.max(max, value.revenue), 0) * 100 : 4)}%` }} /><small>{item.date.slice(5)}</small></div>)}</div></div><div className="studio-panel analytics-ranking"><div className="panel-head"><h2>类目与店铺</h2></div>{analytics.categories.map((item) => <p key={item.name}><span>{item.name} · {item.sales} 件</span><b>{money(item.revenue)}</b></p>)}{analytics.topShops.map((item) => <p key={item.name}><span>{item.name} · {item.orders} 单</span><b>{money(item.revenue)}</b></p>)}</div></section>}
      {analytics && <section className="admin-analytics-grid"><div className="studio-panel analytics-ranking"><div className="panel-head"><h2>连续转化漏斗</h2><span>同一访客顺序路径</span></div><p><span>浏览作品</span><b>{analytics.funnel.views}</b></p><p><span>加入购物车 · {analytics.funnel.viewToCartRate}% · 流失 {analytics.funnel.cartDropOff}</span><b>{analytics.funnel.addCarts}</b></p><p><span>进入结算 · {analytics.funnel.cartToCheckoutRate}% · 流失 {analytics.funnel.checkoutDropOff}</span><b>{analytics.funnel.checkouts}</b></p><p><span>完成支付 · {analytics.funnel.checkoutToPaidRate}% · 流失 {analytics.funnel.paymentDropOff}</span><b>{analytics.funnel.paidBuyers}</b></p></div><div className="studio-panel analytics-ranking"><div className="panel-head"><h2>渠道归因</h2><span>行为与订单合并</span></div>{analytics.channels.map((item) => <p key={item.channel}><span>{item.channel} · {item.visitors} 访客 · 加购 {item.visitorToCartRate}% · 支付 {item.checkoutToPaidRate}%</span><b>{money(item.revenue)} · {item.paidOrders} 单</b></p>)}{!analytics.channels.length && <p><span>暂无渠道行为数据</span></p>}</div></section>}
      {analytics && <><div className="metric-grid analytics-quality"><Metric label="支付客单价" value={money(analytics.quality.averageOrderValue)} trend={`${analytics.quality.paidOrders} 笔已支付订单`} /><Metric label="平均件单价" value={money(analytics.quality.averageItemValue)} trend={`退款率 ${analytics.quality.refundRate}%`} /><Metric label="售后申请率" value={`${analytics.quality.afterSaleRate}%`} trend={`${analytics.quality.refundOrders} 笔退款 · ${money(analytics.quality.refundAmount)}`} /><Metric label="平均发货时效" value={`${analytics.quality.fulfillmentHours} 小时`} trend={`新客 ${analytics.customers.new} · 复购客 ${analytics.customers.repeat}`} /></div><section className="admin-analytics-grid"><div className="studio-panel analytics-ranking"><div className="panel-head"><h2>作品效率</h2><span>浏览到成交</span></div>{analytics.productPerformance.map((item) => <p key={item.id}><span>{item.title} · {item.views} 浏览 · {item.sales} 件 · {item.conversionRate}%</span><b>{money(item.revenue)}</b></p>)}{!analytics.productPerformance.length && <p><span>暂无作品成交数据</span></p>}</div><div className="studio-panel analytics-ranking"><div className="panel-head"><h2>复购分析</h2></div><p><span>本周期新客</span><b>{analytics.customers.new}</b></p><p><span>复购客 / 订单</span><b>{analytics.customers.repeat} / {analytics.customers.repeatOrders}</b></p><p><span>复购率</span><b>{analytics.customers.repeatRate}%</b></p><p><span>复购交易额</span><b>{money(analytics.customers.repeatRevenue)}</b></p></div></section></>}
      <section className="studio-panel admin-operations">
        <div className="panel-head"><h2>平台运营</h2><span>{announcements.length} 条公告 · {campaigns.length} 个活动</span></div>
        <div className="admin-operation-grid"><div><h3>发布公告</h3><input value={announcementDraft.title} maxLength={80} onChange={(event) => setAnnouncementDraft({ ...announcementDraft, title: event.target.value })} placeholder="公告标题" /><textarea value={announcementDraft.content} maxLength={500} onChange={(event) => setAnnouncementDraft({ ...announcementDraft, content: event.target.value })} placeholder="公告内容" /><div><select value={announcementDraft.audience} onChange={(event) => setAnnouncementDraft({ ...announcementDraft, audience: event.target.value })}><option value="all">全部用户</option><option value="buyer">买家</option><option value="seller">卖家</option></select><select value={announcementDraft.status} onChange={(event) => setAnnouncementDraft({ ...announcementDraft, status: event.target.value })}><option value="draft">保存草稿</option><option value="published">立即发布</option></select><button className="primary" disabled={!announcementDraft.title || !announcementDraft.content} onClick={() => void saveAnnouncement()}>保存</button></div></div><div><h3>创建平台活动</h3><input value={campaignDraft.name} maxLength={80} onChange={(event) => setCampaignDraft({ ...campaignDraft, name: event.target.value })} placeholder="活动名称" /><div className="campaign-rule"><input type="number" min="0" value={campaignDraft.threshold} onChange={(event) => setCampaignDraft({ ...campaignDraft, threshold: event.target.value })} placeholder="满额门槛" /><input type="number" min="0.01" step="0.01" value={campaignDraft.discount} onChange={(event) => setCampaignDraft({ ...campaignDraft, discount: event.target.value })} placeholder="优惠金额" /></div><div className="campaign-rule"><input type="number" min="0" step="0.01" value={campaignDraft.budget} onChange={(event) => setCampaignDraft({ ...campaignDraft, budget: event.target.value })} placeholder="活动预算（留空不限）" /><input type="number" min="1" value={campaignDraft.totalUsageLimit} onChange={(event) => setCampaignDraft({ ...campaignDraft, totalUsageLimit: event.target.value })} placeholder="总核销上限（留空不限）" /></div><div className="campaign-rule"><input type="number" min="1" value={campaignDraft.perUserUsageLimit} onChange={(event) => setCampaignDraft({ ...campaignDraft, perUserUsageLimit: event.target.value })} placeholder="每人限用次数" /><span className="campaign-hint">预算按优惠金额预占，订单取消会自动释放。</span></div><div><select value={campaignDraft.type} onChange={(event) => setCampaignDraft({ ...campaignDraft, type: event.target.value as typeof campaignDraft.type })}><option value="coupon">平台券</option><option value="full_reduction">满减活动</option></select><select value={campaignDraft.status} onChange={(event) => setCampaignDraft({ ...campaignDraft, status: event.target.value })}><option value="draft">保存草稿</option><option value="active">立即启用</option></select><button className="primary" disabled={!campaignDraft.name || !campaignDraft.discount} onClick={() => void saveCampaign()}>保存</button></div><div className="admin-operation-list">{campaigns.slice(0, 4).map((item) => <span key={item.id}>{item.name} · 已核销 {item.redemptions} 次 · {money(item.spent)}</span>)}</div></div></div>
        {!!campaigns.length && <div className="campaign-performance">{campaigns.slice(0, 6).map((item) => <article key={item.id}><header><b>{item.name}</b><span>{item.status === "active" ? "生效中" : item.status === "draft" ? "草稿" : "已结束"}</span></header><p>核销 {item.redemptions} 次 · 领取核销 {item.redemptionRate}% · 冲销 {item.reversed} 次</p><p>优惠成本 <b>{money(item.spent)}</b> · 归因交易额 <b>{money(item.attributedRevenue)}</b> · ROI <b>{item.roi === null ? "-" : `${item.roi}x`}</b></p><small>归因订单 {item.attributedOrders} · 归因客单 {money(item.averageOrderValue)} · 预算 {item.budget === null ? "不限" : `${money(item.budget)}，剩余 ${money(item.budgetRemaining || 0)}`}</small></article>)}</div>}
        {!!campaigns.length && <div className="campaign-actions">{campaigns.map((item) => <div key={item.id}><span>{item.name}</span><button className="secondary" onClick={() => editCampaign(item)}>编辑</button>{item.status !== "ended" && <button className="danger" onClick={() => endCampaign(item.id)}>结束活动</button>}</div>)}</div>}
        {!!announcements.length && <div className="admin-operation-list">{announcements.slice(0, 4).map((item) => <span key={item.id}>{item.title} · {item.status}</span>)}</div>}
      </section>
      <CouponOperations />
      <SearchOperations />
      <ServiceAutomationOperations />
      <ActivityOperations />
      <section className="studio-panel governance-operations">
        <div className="panel-head"><h2>治理运营</h2><button className="secondary" onClick={() => void exportGovernance()}>导出治理数据</button></div>
        <div className="admin-operation-grid"><div><h3>审核规则</h3><input value={ruleDraft.name} maxLength={80} onChange={(event) => setRuleDraft({ ...ruleDraft, name: event.target.value })} placeholder="规则名称" /><input value={ruleDraft.keyword} maxLength={80} onChange={(event) => setRuleDraft({ ...ruleDraft, keyword: event.target.value })} placeholder="命中关键词（可选）" /><div><select value={ruleDraft.action} onChange={(event) => setRuleDraft({ ...ruleDraft, action: event.target.value as typeof ruleDraft.action })}><option value="manual_review">转人工审核</option><option value="reject">自动驳回</option></select><button className="primary" disabled={!ruleDraft.name} onClick={() => void saveRule()}>保存规则</button></div><div className="admin-operation-list">{governanceRules.slice(0, 5).map((item) => <span key={item.id}>{item.name} · {item.keyword || "通用"} · {item.action} · {item.enabled ? "启用" : "停用"}</span>)}</div></div><div><h3>处罚模板</h3><input value={templateDraft.name} maxLength={80} onChange={(event) => setTemplateDraft({ ...templateDraft, name: event.target.value })} placeholder="模板名称" /><textarea value={templateDraft.reason} maxLength={300} onChange={(event) => setTemplateDraft({ ...templateDraft, reason: event.target.value })} placeholder="处罚说明" /><div><select value={templateDraft.targetType} onChange={(event) => { const targetType = event.target.value as typeof templateDraft.targetType; setTemplateDraft({ ...templateDraft, targetType, action: targetType === "product" ? "unlist_product" : targetType === "shop" ? "pause_shop" : "disable_user" }); }}><option value="product">作品</option><option value="shop">店铺</option><option value="user">用户</option></select><select value={templateDraft.action} onChange={(event) => setTemplateDraft({ ...templateDraft, action: event.target.value })}><option value="unlist_product">下架作品</option><option value="pause_shop">暂停店铺</option><option value="disable_user">停用用户</option><option value="warning">警告</option></select><button className="primary" disabled={!templateDraft.name || !templateDraft.reason} onClick={() => void saveTemplate()}>保存模板</button></div><div className="admin-operation-list">{enforcementTemplates.slice(0, 5).map((item) => <span key={item.id}>{item.name} · {item.action} · {item.enabled ? "启用" : "停用"}</span>)}</div></div></div>
        <div className="governance-task-list"><h3>审核任务分派</h3>{governanceTasks.filter((item) => item.status !== "completed").slice(0, 12).map((task) => <div key={task.id}><span><b>{task.type}</b><small>{task.targetId} · {task.createdAt}</small></span><select value={task.assigneeId || ""} onChange={(event) => void assignTask(task.id, event.target.value)}><option value="">未分派</option>{governanceAdmins.map((admin) => <option key={admin.id} value={admin.id}>{admin.name}</option>)}</select><em>{task.status === "in_progress" ? `处理中：${task.assignee || ""}` : "待处理"}</em></div>)}{!governanceTasks.some((item) => item.status !== "completed") && <p>暂无待分派任务。</p>}</div>
      </section>
      <GovernanceDeepOperations />
      <GovernanceServiceInsights />
      <section className="studio-panel">
        <div className="panel-head"><h2>待处理举报</h2><span>{reports.filter((item) => item.status === "pending").length} 条</span></div>
        {reports.filter((item) => item.status === "pending").map((report) => (
          <article className="seller-order" key={report.id}>
            <span><b>{report.reason}</b><small>{report.targetType} · {report.targetId} · {report.reporter}</small><small>{report.detail || "未补充说明"}</small></span>
            <div><button className="secondary" onClick={() => void resolveReport(report.id, "dismissed")}>驳回</button><button className="primary" onClick={() => void resolveReport(report.id, "resolved")}>处理并下架</button></div>
          </article>
        ))}
        {!reports.some((item) => item.status === "pending") && <p>暂无待处理举报。</p>}
      </section>
      <section className="studio-panel">
        <div className="panel-head"><h2>作品审核</h2><span>{products.length} 件</span><div className="governance-bulk"><label><input type="checkbox" checked={products.length > 0 && products.every((product) => selectedProducts.includes(product.id))} onChange={(event) => setSelectedProducts(event.target.checked ? products.map((product) => product.id) : [])} />全选</label><button className="secondary" disabled={!selectedProducts.length} onClick={() => void bulkModerate("approved")}>批量通过</button><button className="danger" disabled={!selectedProducts.length} onClick={() => void bulkModerate("rejected")}>批量驳回</button></div></div>
        {products.map((product) => (
          <article className="seller-order" key={product.id}>
            <span><label className="governance-select"><input type="checkbox" checked={selectedProducts.includes(product.id)} onChange={(event) => setSelectedProducts((items) => event.target.checked ? [...items, product.id] : items.filter((id) => id !== product.id))} />选择</label><b>{product.title}</b><small>{product.shop} · {product.moderationStatus} · {product.status}</small>{product.reason && <small>{product.reason}</small>}</span>
            <div><button className="secondary" onClick={() => void moderate(product.id, "approved")}>通过</button><button className="danger" onClick={() => void moderate(product.id, "rejected")}>驳回并下架</button></div>
          </article>
        ))}
      </section>
      <AdminFinanceOperations />
      <AdminServiceManagement />
    </main>
  );
}

function AccountSecurity({ account, onBack }: { account: Account; onBack: () => void }) {
  const [security, setSecurity] = useState<{ phone?: string; email?: string; phoneVerified: boolean; emailVerified: boolean; passwordChangedAt?: string; lastLoginAt?: string } | null>(null);
  const [sessions, setSessions] = useState<{ id: string; current: boolean; createdAt: string; lastSeenAt?: string; expiresAt: string; userAgent?: string; ipAddress?: string }[]>([]);
  const [events, setEvents] = useState<{ success: boolean; reason?: string; ipAddress?: string; createdAt: string }[]>([]);
  const [destination, setDestination] = useState("");
  const [code, setCode] = useState("");
  const [developmentCode, setDevelopmentCode] = useState("");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [notice, setNotice] = useState("");
  const load = async () => {
    const response = await fetch(`${API_BASE}/api/auth/security`, { credentials: "include" });
    const payload = await response.json().catch(() => null) as { security?: typeof security; sessions?: typeof sessions; loginEvents?: typeof events } | null;
    if (response.ok && payload?.security) {
      setSecurity(payload.security);
      setSessions(payload.sessions || []);
      setEvents(payload.loginEvents || []);
    }
  };
  useEffect(() => { void load(); }, []);
  const requestCode = async (value: string) => {
    setNotice("");
    const response = await fetch(`${API_BASE}/api/auth/request-verification`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ destination: value, purpose: "contact_verify" }) });
    const payload = await response.json().catch(() => ({})) as { error?: string; developmentCode?: string };
    if (!response.ok) return setNotice(payload.error || "验证码发送失败");
    setDestination(value);
    setDevelopmentCode(payload.developmentCode || "");
    setNotice("验证码已发送");
  };
  const verifyContact = async () => {
    const response = await fetch(`${API_BASE}/api/auth/verify-contact`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ destination, code }) });
    const payload = await response.json().catch(() => ({})) as { error?: string };
    if (!response.ok) return setNotice(payload.error || "验证失败");
    setCode(""); setDevelopmentCode(""); setNotice("联系方式已验证"); void load();
  };
  const changePassword = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const response = await fetch(`${API_BASE}/api/auth/change-password`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ currentPassword, password: newPassword }) });
    const payload = await response.json().catch(() => ({})) as { error?: string };
    if (!response.ok) return setNotice(payload.error || "密码修改失败");
    setCurrentPassword(""); setNewPassword(""); setNotice("密码已修改，其他设备已退出登录"); void load();
  };
  const revokeSession = async (sessionId: string) => {
    const response = await fetch(`${API_BASE}/api/auth/sessions/revoke`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ sessionId }) });
    const payload = await response.json().catch(() => ({})) as { error?: string };
    if (!response.ok) return setNotice(payload.error || "会话移除失败");
    setNotice("设备已退出登录"); void load();
  };
  return <main className="container page section security-page">
    <button className="back" onClick={onBack}><ArrowLeft size={18} />返回</button>
    <div className="page-title"><div><h1>账号与安全</h1><p>{account.name} 的账号安全设置</p></div></div>
    {notice && <p className="auth-error">{notice}</p>}
    <section className="security-card"><h2>联系方式验证</h2>
      {security?.phone && <div className="security-contact"><span>手机号：{security.phone}</span><b>{security.phoneVerified ? "已验证" : "未验证"}</b>{!security.phoneVerified && <button className="secondary" onClick={() => void requestCode(security.phone!)}>发送验证码</button>}</div>}
      {security?.email && <div className="security-contact"><span>邮箱：{security.email}</span><b>{security.emailVerified ? "已验证" : "未验证"}</b>{!security.emailVerified && <button className="secondary" onClick={() => void requestCode(security.email!)}>发送验证码</button>}</div>}
      {destination && <div className="security-verification"><input inputMode="numeric" maxLength={6} value={code} onChange={(event) => setCode(event.target.value.replace(/\D/g, ""))} placeholder="请输入 6 位验证码" /> <button className="primary" onClick={() => void verifyContact()}>确认验证</button></div>}
      {developmentCode && <small className="security-dev-code">开发环境验证码：{developmentCode}</small>}
    </section>
    <section className="security-card"><h2>修改密码</h2><form className="security-password" onSubmit={changePassword}><input type="password" value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} placeholder="当前密码" autoComplete="current-password" required /><input type="password" minLength={8} value={newPassword} onChange={(event) => setNewPassword(event.target.value)} placeholder="新密码，至少 8 位" autoComplete="new-password" required /><button className="primary">更新密码</button></form></section>
    <section className="security-card"><div className="panel-head"><h2>登录设备</h2><span>{sessions.length} 个会话</span></div>{sessions.map((item) => <div className="security-session" key={item.id}><span><b>{item.current ? "当前设备" : "已登录设备"}</b><small>{item.ipAddress || "未知地址"} · 最近活动 {item.lastSeenAt || item.createdAt}</small></span>{!item.current && <button className="secondary" onClick={() => void revokeSession(item.id)}>退出设备</button>}</div>)}</section>
    <section className="security-card"><div className="panel-head"><h2>最近登录</h2></div>{events.length ? events.map((item, index) => <div className="security-session" key={`${item.createdAt}-${index}`}><span><b>{item.success ? "登录成功" : "登录失败"}</b><small>{item.ipAddress || "未知地址"} · {item.createdAt}{item.reason ? ` · ${item.reason}` : ""}</small></span></div>) : <p>暂无登录记录。</p>}</section>
  </main>;
}

function ProfileSettings({
  account,
  onBack,
  onSecurity,
  onFavorites,
  onOrders,
  onCoupons,
  onFollowing,
  onAccountUpdated,
  onAccountDeleted,
}: {
  account: Account;
  onBack: () => void;
  onSecurity: () => void;
  onFavorites: () => void;
  onOrders: () => void;
  onCoupons: () => void;
  onFollowing: () => void;
  onAccountUpdated: (changes: Partial<Account>) => void;
  onAccountDeleted: () => void;
}) {
  const [name, setName] = useState(account.name);
  const [bio, setBio] = useState("");
  const [phone, setPhone] = useState(account.phone || "");
  const [email, setEmail] = useState(account.email || "");
  const [currentPassword, setCurrentPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [reason, setReason] = useState("");
  const [notice, setNotice] = useState("");
  const [saving, setSaving] = useState(false);
  const [cancelling, setCancelling] = useState(false);

  useEffect(() => {
    fetch(`${API_BASE}/api/profile`, { credentials: "include" })
      .then((response) => response.ok ? response.json() : Promise.reject())
      .then((payload: { profile?: { name: string; bio: string; phone?: string; email?: string } }) => {
        if (!payload.profile) return;
        setName(payload.profile.name);
        setBio(payload.profile.bio || "");
        setPhone(payload.profile.phone || "");
        setEmail(payload.profile.email || "");
      })
      .catch(() => setNotice("个人资料加载失败"));
  }, []);

  const saveProfile = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSaving(true);
    setNotice("");
    try {
      const response = await fetch(`${API_BASE}/api/profile`, {
        method: "PUT",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, bio, phone, email, currentPassword }),
      });
      const payload = await response.json().catch(() => ({})) as { error?: string; profile?: { name: string; phone?: string; email?: string } };
      if (!response.ok || !payload.profile) {
        setNotice(payload.error || "个人资料保存失败");
        return;
      }
      setCurrentPassword("");
      onAccountUpdated({ name: payload.profile.name, phone: payload.profile.phone, email: payload.profile.email });
      setNotice("个人资料已保存");
    } catch {
      setNotice("个人资料保存失败");
    } finally {
      setSaving(false);
    }
  };

  const deleteAccount = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setCancelling(true);
    setNotice("");
    try {
      const response = await fetch(`${API_BASE}/api/auth/delete-account`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ currentPassword, confirmation, reason }),
      });
      const payload = await response.json().catch(() => ({})) as { error?: string };
      if (!response.ok) {
        setNotice(payload.error || "账号注销失败");
        return;
      }
      onAccountDeleted();
    } catch {
      setNotice("账号注销失败");
    } finally {
      setCancelling(false);
    }
  };

  return <main className="container page section security-page profile-page">
    <button className="back" onClick={onBack}><ArrowLeft size={18} />返回</button>
    <div className="page-title"><div><h1>个人资料</h1><p>管理公开资料和登录联系方式</p></div></div>
    {notice && <p className="auth-error">{notice}</p>}
    {account.role === "buyer" && (
      <section className="profile-services" aria-label="我的服务">
        <button type="button" onClick={onSecurity}><Settings2 size={20} /><span><b>账号与安全</b><small>管理密码、验证方式与登录设备</small></span><ChevronRight size={18} /></button>
        <button type="button" onClick={onOrders}><Package size={20} /><span><b>我的订单</b><small>查看订单、物流与售后进度</small></span><ChevronRight size={18} /></button>
        <button type="button" onClick={onFavorites}><Heart size={20} /><span><b>我的收藏</b><small>查看收藏的手作作品</small></span><ChevronRight size={18} /></button>
        <button type="button" onClick={onCoupons}><CreditCard size={20} /><span><b>优惠券包</b><small>查看可用优惠与领取记录</small></span><ChevronRight size={18} /></button>
        <button type="button" onClick={onFollowing}><Store size={20} /><span><b>关注店铺</b><small>查看和管理已关注的创作者</small></span><ChevronRight size={18} /></button>
      </section>
    )}
    <section className="security-card">
      <h2>基本资料</h2>
      <form className="profile-form" onSubmit={saveProfile}>
        <label>昵称<input value={name} maxLength={30} onChange={(event) => setName(event.target.value)} required /></label>
        <label className="profile-form-wide">个人简介<textarea value={bio} maxLength={300} onChange={(event) => setBio(event.target.value)} placeholder="介绍你的手作偏好或店铺理念" /></label>
        <label>手机号<input inputMode="numeric" value={phone} onChange={(event) => setPhone(event.target.value)} placeholder="至少保留一种联系方式" /></label>
        <label>邮箱<input type="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="至少保留一种联系方式" /></label>
        <label className="profile-form-wide">当前密码（仅修改手机号或邮箱时必填）<input type="password" autoComplete="current-password" value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} /></label>
        <div className="profile-form-wide"><button className="primary" disabled={saving}>{saving ? "保存中..." : "保存资料"}</button></div>
      </form>
    </section>
    <section className="security-card danger-zone">
      <h2>注销账号</h2>
      <p>注销后将退出所有设备，个人资料和收货地址会被清除；历史订单将保留用于交易记录。存在进行中订单或售后时无法注销。</p>
      <form className="profile-form" onSubmit={deleteAccount}>
        <label>当前密码<input type="password" autoComplete="current-password" value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} required /></label>
        <label>确认文字<input value={confirmation} onChange={(event) => setConfirmation(event.target.value)} placeholder="请输入：注销账号" required /></label>
        <label className="profile-form-wide">注销原因（可选）<textarea value={reason} maxLength={300} onChange={(event) => setReason(event.target.value)} placeholder="帮助我们改进服务" /></label>
        <div className="profile-form-wide"><button className="danger-button" disabled={cancelling}>{cancelling ? "正在注销..." : "确认注销账号"}</button></div>
      </form>
    </section>
  </main>;
}

function Marketplace({
  account,
  onLogout,
  onAccountUpdated,
  onAccountDeleted,
  isGuest = false,
  onAuth,
}: {
  account: Account;
  onLogout: () => void;
  onAccountUpdated: (changes: Partial<Account>) => void;
  onAccountDeleted: () => void;
  isGuest?: boolean;
  onAuth: () => void;
}) {
  const [data, setData] = usePersistedData(account, isGuest);
  const initialProductId = Number(
    new URLSearchParams(window.location.search).get("product"),
  );
  const initialView = new URLSearchParams(window.location.search).get("view");
  const canRestoreInitialView = account.role === "buyer"
    ? buyerRestorableViews.includes(initialView as MarketplaceView)
    : sellerRestorableViews.includes(initialView as MarketplaceView);
  const [view, setView] = useState<MarketplaceView>(() =>
    account.role === "buyer" && Number.isInteger(initialProductId) && initialProductId > 0
      ? "product"
      : canRestoreInitialView
        ? initialView as MarketplaceView
        : account.role === "seller"
          ? "studio"
          : "home",
  );
  const [selectedId, setSelectedId] = useState(
    Number.isInteger(initialProductId) && initialProductId > 0
      ? initialProductId
      : 1,
  );
  const [productReturnView, setProductReturnView] = useState<typeof view>(
    "discover",
  );
  const [query, setQuery] = useState("");
  const [searchOpen, setSearchOpen] = useState(false);
  const searchRef = useRef<HTMLDivElement>(null);
  const [searchSort, setSearchSort] = useState<"relevance" | "latest" | "price_asc" | "price_desc" | "sales">("relevance");
  const [searchResults, setSearchResults] = useState<Product[] | null>(null);
  const [personalizedProducts, setPersonalizedProducts] = useState<Product[]>([]);
  const [searchMeta, setSearchMeta] = useState<{ originalQuery: string; corrected?: string | null; recommendations: string[]; zeroResult?: { message: string; productId?: string | null } | null }>({ originalQuery: "", recommendations: [] });
  const [searchSuggestions, setSearchSuggestions] = useState<{ value: string; type: "history" | "product" | "tag" | "recommendation" | "trending"; hint: string }[]>([]);
  const [category, setCategory] = useState<Category | "全部">("全部");
  const [notice, setNotice] = useState("");
  const [shippingId, setShippingId] = useState("");
  const [shippingModalOpen, setShippingModalOpen] = useState(false);
  const [sharedOrders, setSharedOrders] = useState<Order[]>([]);
  const [sharedAfterSales, setSharedAfterSales] = useState<AfterSaleRequest[]>([]);
  const [sharedReviews, setSharedReviews] = useState<ProductReview[]>([]);
  const [notificationUnread, setNotificationUnread] = useState(0);
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [platformAnnouncements, setPlatformAnnouncements] = useState<{ id: string; title: string; content: string }[]>([]);
  const [addresses, setAddresses] = useState<BuyerAddress[]>([]);
  const [coupons, setCoupons] = useState<{ id: string; name: string; threshold: number; discount: number; remaining: number; claimed: number; used: number; available: boolean; endsAt?: string }[]>([]);
  const [claimableCoupons, setClaimableCoupons] = useState<{ id: string; name: string; threshold: number; discount: number; claimLimit: number }[]>([]);
  const [visitorKey] = useState(
    () =>
      account.id === guestAccount.id
        ? `guest-${Date.now()}-${Math.random().toString(36).slice(2)}`
        : account.id,
  );
  const [trafficChannel] = useState(() => new URLSearchParams(window.location.search).get("utm_source") || (document.referrer ? "referral" : "direct"));
  const refreshCoupons = async () => { const response = await fetch(`${API_BASE}/api/buyer/coupons`, { credentials: "include" }); if (response.ok) { const payload = (await response.json()) as { coupons: typeof coupons; claimable: typeof claimableCoupons }; setCoupons(payload.coupons); setClaimableCoupons(payload.claimable); } };
  const cartCount = data.cart.reduce((sum, item) => sum + item.quantity, 0);
  useEffect(() => {
    if (isGuest) return;
    const load = () => fetch(`${API_BASE}/api/notifications`, { credentials: "include" })
      .then((response) => (response.ok ? response.json() : null))
      .then((payload: { unread: number; notifications: NotificationItem[] } | null) => {
        setNotificationUnread(payload?.unread || 0);
        setNotifications(payload?.notifications || []);
      })
      .catch(() => undefined);
    void load();
    const timer = window.setInterval(load, 30000);
    return () => window.clearInterval(timer);
  }, [account.id, isGuest]);
  useEffect(() => {
    fetch(`${API_BASE}/api/platform/announcements`, { credentials: "include" })
      .then((response) => (response.ok ? response.json() : Promise.reject()))
      .then((payload: { announcements: { id: string; title: string; content: string }[] }) => setPlatformAnnouncements(payload.announcements || []))
      .catch(() => setPlatformAnnouncements([]));
  }, [account.id]);
  useEffect(() => {
    const url = new URL(window.location.href);
    if (view === "product") url.searchParams.set("product", String(selectedId));
    else url.searchParams.delete("product");
    if (view !== "product")
      url.searchParams.set("view", view);
    else url.searchParams.delete("view");
    const nextUrl = `${url.pathname}${url.search}${url.hash}`;
    if (nextUrl !== `${window.location.pathname}${window.location.search}${window.location.hash}`)
      window.history.replaceState(null, "", nextUrl);
  }, [view, selectedId]);
  useEffect(() => {
    if (view !== "discover") return;
    const controller = new AbortController();
    const params = new URLSearchParams({ q: query, category: category === "全部" ? "" : category, sort: searchSort });
    fetch(`${API_BASE}/api/search?${params.toString()}`, { credentials: "include", signal: controller.signal })
      .then((response) => response.ok ? response.json() : Promise.reject())
      .then((payload: { products: Product[]; originalQuery: string; corrected?: string | null; recommendations?: string[]; personalizedProducts?: Product[]; zeroResult?: { message: string; productId?: string | null } | null }) => {
        setSearchResults(payload.products);
        setPersonalizedProducts(payload.personalizedProducts || []);
        setSearchMeta({ originalQuery: payload.originalQuery, corrected: payload.corrected, recommendations: payload.recommendations || [], zeroResult: payload.zeroResult });
      })
      .catch(() => { if (!controller.signal.aborted) { setSearchResults(null); setPersonalizedProducts([]); setSearchMeta({ originalQuery: "", recommendations: [] }); } });
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
      fetch(`${API_BASE}/api/search/suggestions?q=${encodeURIComponent(query)}`, { credentials: "include", signal: controller.signal })
        .then((response) => response.ok ? response.json() : Promise.reject())
        .then((payload: { suggestions?: typeof searchSuggestions }) => setSearchSuggestions(payload.suggestions || []))
        .catch(() => { if (!controller.signal.aborted) setSearchSuggestions([]); });
    }, 140);
    return () => { controller.abort(); window.clearTimeout(timer); };
  }, [account.role, query]);
  useEffect(() => {
    const closeWhenClickingOutside = (event: PointerEvent) => {
      if (searchRef.current && !searchRef.current.contains(event.target as Node)) setSearchOpen(false);
    };
    document.addEventListener("pointerdown", closeWhenClickingOutside);
    return () => document.removeEventListener("pointerdown", closeWhenClickingOutside);
  }, []);
  const show = (next: typeof view) => {
    const buyerOnly = [
      "cart",
      "checkout",
      "orders",
      "favorites",
      "coupons",
      "following",
    ];
    const sellerOnly = ["shop", "studio"];
    const allowed =
      account.role === "buyer"
        ? !sellerOnly.includes(next)
        : !buyerOnly.includes(next);
    setView(allowed ? next : account.role === "buyer" ? "home" : "studio");
    window.scrollTo({ top: 0, behavior: "smooth" });
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
    if (!response.ok) throw new Error("订单加载失败");
    const payload = (await response.json()) as { orders: Order[] };
    setSharedOrders(payload.orders);
    const afterSalesResponse = await fetch(`${API_BASE}/api/after-sales/${endpoint}`, {
      credentials: "include",
    });
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
      const reviewsPayload = (await reviewsResponse.json()) as { reviews: ProductReview[] };
      setSharedReviews(reviewsPayload.reviews);
    }
  };
  const refreshAddresses = async () => {
    if (isGuest || account.role !== "buyer") return;
    const response = await fetch(`${API_BASE}/api/addresses`, { credentials: "include" });
    if (!response.ok) throw new Error("地址加载失败");
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
  const checkoutItems = () => data.cart.map((item) => {
    const product = data.products.find((value) => value.id === item.productId);
    return { ...item, catalogId: product?.catalogId };
  });
  const quoteCheckout = async (addressId: string) => {
    const response = await fetch(`${API_BASE}/api/checkout/quote`, {
      method: "POST", credentials: "include", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ items: checkoutItems(), addressId, channel: trafficChannel }),
    });
    const payload = (await response.json()) as { quote?: CheckoutQuote; error?: string };
    if (!response.ok) throw new Error(payload.error || "结算报价失败");
    return payload.quote!;
  };
  const createSharedOrders = async (addressId: string, paymentMethod: PaymentMethod) => {
    const items = checkoutItems();
    if (items.some((item) => !item.catalogId)) {
      toast("部分作品尚未同步，暂时无法结算");
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
    const payload = (await response.json()) as { orders?: Order[]; error?: string };
    if (!response.ok) {
      toast(payload.error || "订单创建失败");
      return null;
    }
    setData((current) => ({ ...current, cart: [] }));
    const createdOrders = payload.orders || [];
    setSharedOrders((current) => [...createdOrders, ...current]);
    const catalogResponse = await fetch(`${API_BASE}/api/catalog/products`);
    if (catalogResponse.ok) {
      const catalogPayload = (await catalogResponse.json()) as { products: Product[] };
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
      toast(payload.error || "支付失败");
      return false;
    }
    if (!payload.payment?.token) {
      toast("支付发起失败");
      return false;
    }
    const confirmation = await fetch(`${API_BASE}/api/orders/${id}/payment-confirm`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ paymentToken: payload.payment.token }),
    });
    const confirmed = (await confirmation.json()) as { orders?: Order[]; error?: string };
    if (!confirmation.ok) {
      toast(confirmed.error || "支付确认失败");
      return false;
    }
    const changed = confirmed.orders?.[0];
    if (changed) setSharedOrders((orders) => orders.map((order) => (order.id === id ? changed : order)));
    toast("支付成功，等待卖家发货");
    return true;
  };
  const shipSharedOrder = async (id: string, draft: ShipmentDraft) => {
    const response = await fetch(`${API_BASE}/api/orders/${id}/ship`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(draft),
    });
    const payload = (await response.json()) as { orders?: Order[]; error?: string };
    if (!response.ok) {
      toast(payload.error || "发货失败");
      return false;
    }
    const changed = payload.orders?.[0];
    if (changed) setSharedOrders((orders) => orders.map((order) => (order.id === id ? changed : order)));
    toast("已发货，物流单号已同步");
    return true;
  };
  const addShipmentEvent = async (id: string, label: string, detail: string) => {
    const response = await fetch(`${API_BASE}/api/orders/${id}/shipment-events`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ label, detail }),
    });
    const payload = (await response.json()) as { orders?: Order[]; error?: string };
    if (!response.ok) {
      toast(payload.error || "物流更新失败");
      return false;
    }
    const changed = payload.orders?.[0];
    if (changed) setSharedOrders((orders) => orders.map((order) => (order.id === id ? changed : order)));
    toast("物流节点已更新");
    return true;
  };
  const updateSharedOrder = async (id: string, action: "receive" | "cancel") => {
    const response = await fetch(`${API_BASE}/api/orders/${id}/${action}`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    });
    const payload = (await response.json()) as { orders?: Order[]; error?: string };
    if (!response.ok) {
      toast(payload.error || "订单更新失败");
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
      toast(payload.error || "售后申请提交失败");
      return false;
    }
    setSharedAfterSales((items) => [...(payload.afterSales || []), ...items]);
    await refreshSharedOrders();
    toast("售后申请已提交");
    return true;
  };
  const createReview = async (id: string, draft: ReviewDraft) => {
    const response = await fetch(`${API_BASE}/api/orders/${id}/review`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(draft),
    });
    const payload = (await response.json()) as { orders?: Order[]; error?: string };
    if (!response.ok) {
      toast(payload.error || "评价提交失败");
      return false;
    }
    const changed = payload.orders?.[0];
    if (changed)
      setSharedOrders((orders) => orders.map((order) => (order.id === id ? changed : order)));
    await refreshSharedOrders();
    toast("评价已提交");
    return true;
  };
  const createReviewFollowup = async (reviewIds: Array<string | number>, content: string) => {
    const responses = await Promise.all(
      reviewIds.map(async (reviewId) => {
        const response = await fetch(`${API_BASE}/api/reviews/${reviewId}/followup`, {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ content }),
        });
        const payload = (await response.json()) as { error?: string };
        return { ok: response.ok, error: payload.error };
      }),
    );
    const failed = responses.find((result) => !result.ok);
    if (failed) {
      toast(failed.error || "追评提交失败");
      return false;
    }
    await refreshSharedOrders();
    toast("追评已提交");
    return true;
  };
  const resolveAfterSale = async (id: string | number, action: "approve" | "reject", responseText: string) => {
    const response = await fetch(`${API_BASE}/api/after-sales/${id}/${action}`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ response: responseText.trim() }),
    });
    const payload = (await response.json()) as { afterSales?: AfterSaleRequest[]; error?: string };
    if (!response.ok) {
      toast(payload.error || "售后处理失败");
      return false;
    }
    const changed = payload.afterSales?.[0];
    if (changed)
      setSharedAfterSales((items) => items.map((item) => (item.id === id ? changed : item)));
    await refreshSharedOrders();
    toast(action === "approve" ? "售后处理已提交" : "售后申请已拒绝");
    return true;
  };
  const submitReturnShipment = async (id: string | number, draft: ReturnShipmentDraft) => {
    const response = await fetch(`${API_BASE}/api/after-sales/${id}/return-shipment`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(draft),
    });
    const payload = (await response.json()) as { afterSales?: AfterSaleRequest[]; error?: string };
    if (!response.ok) {
      toast(payload.error || "退货物流提交失败");
      return false;
    }
    const changed = payload.afterSales?.[0];
    if (changed) setSharedAfterSales((items) => items.map((item) => (item.id === id ? changed : item)));
    await refreshSharedOrders();
    toast("退货物流已提交，等待卖家确认收货");
    return true;
  };
  const receiveReturn = async (id: string | number, responseText: string) => {
    const response = await fetch(`${API_BASE}/api/after-sales/${id}/receive-return`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ response: responseText.trim() }),
    });
    const payload = (await response.json()) as { afterSales?: AfterSaleRequest[]; error?: string };
    if (!response.ok) {
      toast(payload.error || "确认收货失败");
      return false;
    }
    const changed = payload.afterSales?.[0];
    if (changed) setSharedAfterSales((items) => items.map((item) => (item.id === id ? changed : item)));
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
    const payload = (await response.json()) as { reviews?: ProductReview[]; error?: string };
    if (!response.ok) {
      toast(payload.error || "评价回复失败");
      return false;
    }
    const changed = payload.reviews?.[0];
    if (changed)
      setSharedReviews((items) => items.map((item) => (item.id === id ? changed : item)));
    toast("评价回复已发送");
    return true;
  };
  const selected =
    data.products.find((p) => p.id === selectedId) || data.products[0];
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
  const updateSharedCart = async (id: number, quantity: number, variants: Record<string, string> = {}) => {
    const product = data.products.find((item) => item.id === id);
    if (!product?.catalogId) return toast("作品尚未同步");
    const response = await fetch(`${API_BASE}/api/cart`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ catalogId: product.catalogId, quantity, variants, channel: trafficChannel }) });
    if (!response.ok) return toast("购物车更新失败");
    applyBuyerState(await response.json());
  };
  const openProduct = (id: number) => {
    const product = data.products.find((item) => item.id === id);
    if (product?.catalogId) fetch(`${API_BASE}/api/analytics/events`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ type: "product_view", productId: product.catalogId, visitorKey, channel: trafficChannel }) }).catch(() => undefined);
    if (account.role === "buyer" && product?.analyticsShopId) {
      fetch(`${API_BASE}/api/analytics/shops/${product.analyticsShopId}/visits`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ visitorKey }),
      }).catch(() => undefined);
    }
    setSelectedId(id);
    setProductReturnView(view);
    show("product");
  };
  const applyBuyerState = (state: Pick<AppData, "cart" | "favorites" | "followedShops">) =>
    setData((current) => ({ ...current, ...state }));
  const toggleFavorite = async (id: number) => {
    const product = data.products.find((item) => item.id === id);
    if (!product?.catalogId) return toast("作品尚未同步");
    const response = await fetch(`${API_BASE}/api/favorites/${product.catalogId}`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: "{}" });
    if (!response.ok) return toast("收藏更新失败");
    applyBuyerState(await response.json());
  };
  const toggleShopFollow = async (shop: FollowedShop) => {
    if (isGuest) return toast("请登录后关注店铺");
    const product = data.products.find((item) => item.shopId === shop.id);
    const shopId = typeof shop.id === "string" ? shop.id : product?.analyticsShopId;
    if (!shopId) return toast("店铺尚未同步");
    const response = await fetch(`${API_BASE}/api/follows/${shopId}`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: "{}" });
    if (!response.ok) return toast("关注更新失败");
    const state = await response.json() as Pick<AppData, "cart" | "favorites" | "followedShops">;
    applyBuyerState(state);
    toast(state.followedShops.some((item) => String(item.id) === String(shopId)) ? "已关注店铺" : "已取消关注");
  };
  const reset = () => {
    setData(createInitialData(account));
    toast("已恢复初始数据");
  };
  const nav = (target: typeof view, label: string) => (
    <button
      data-testid={`nav-${target}`}
      className={view === target ? "nav-active" : ""}
      onClick={() => show(target)}
    >
      {label}
    </button>
  );
  return (
    <div className="app-shell">
      <header className="site-header">
        <div className="header-main container">
          <button
            className="brand"
            onClick={() => show("home")}
            aria-label="回到首页"
          >
            手作<span>集</span>
          </button>
          {account.role === "buyer" && (
            <div className="search" ref={searchRef}>
              <Search size={19} />
              <input
                value={query}
                onFocus={() => setSearchOpen(true)}
                onChange={(e) => { setQuery(e.target.value); setSearchOpen(true); }}
                onKeyDown={(e) => {
                  if (e.key === "Escape") setSearchOpen(false);
                  if (e.key === "Enter") { setSearchOpen(false); show("discover"); }
                }}
                placeholder="搜索手作、原创设计、复古好物"
              />
              <button onClick={() => { setSearchOpen(false); show("discover"); }}>搜索</button>
              {searchOpen && query.trim() && searchSuggestions.length > 0 && <div className="search-autocomplete" role="listbox" aria-label="搜索建议">
                {searchSuggestions.map((item) => <button key={`${item.type}-${item.value}`} role="option" onMouseDown={(event) => event.preventDefault()} onClick={() => { setQuery(item.value); setSearchSuggestions([]); setSearchOpen(false); show("discover"); }}><span>{item.value}</span><small>{item.hint}</small></button>)}
              </div>}
            </div>
          )}
          <div className="header-actions">
            {isGuest ? (
              <button data-testid="open-auth" className="logout-button" onClick={onAuth}>
                登录 / 注册
              </button>
            ) : (
              <>
                <button className="account-name-trigger" onClick={() => show("profile")}>{account.name}</button>
                <IconButton icon={LogOut} label="退出" onClick={onLogout} />
              </>
            )}
            {account.role === "buyer" && (
              <>
                <div className="cart-wrap">
                  <IconButton
                    icon={MessageCircle}
                    label="消息"
                    onClick={() => show("messages")}
                  />
                  {notificationUnread > 0 && <span>{notificationUnread}</span>}
                </div>
                <div className="cart-wrap">
                  <IconButton
                  icon={ShoppingBag}
                  label="购物袋"
                  testId="open-cart"
                    onClick={() => show("cart")}
                  />
                  {cartCount > 0 && <span data-testid="cart-count">{cartCount}</span>}
                </div>
              </>
            )}
          </div>
        </div>
        <nav className="top-nav container">
          {account.role === "buyer" ? (
            <>
              {nav("home", "首页")}
              {nav("discover", "发现好物")}
            </>
          ) : (
            <>
              {nav("studio", "店主工作台")}
              {nav("shop", "店铺主页")}
            </>
          )}
        </nav>
      </header>
      {!!platformAnnouncements.length && <section className="platform-announcement"><div className="container">{platformAnnouncements.slice(0, 1).map((item) => <span key={item.id}><b>{item.title}</b>{item.content}</span>)}</div></section>}
      <main>
        {view === "home" && (
          <Home
            products={data.products.filter((product) => product.listed !== false)}
            favorites={data.favorites}
            onOpen={openProduct}
            onFavorite={toggleFavorite}
            onCategory={(c) => {
              setCategory(c);
              show("discover");
            }}
          />
        )}
        {view === "discover" && (
          <Discover
            products={searchResults ?? data.products.filter((product) => product.listed !== false)}
            personalizedProducts={personalizedProducts}
            query={query}
            searchMeta={searchMeta}
            serverFiltered={searchResults !== null}
            category={category}
            sort={searchSort}
            favorites={data.favorites}
            onOpen={openProduct}
            onFavorite={toggleFavorite}
            onCategory={setCategory}
            onSort={setSearchSort}
            onQueryChange={setQuery}
          />
        )}
        {view === "product" && (
          <ProductDetail
            product={selected}
            favorite={data.favorites.includes(selected.id)}
            onBack={() => show(productReturnView)}
            onFavorite={toggleFavorite}
            shopFollowed={data.followedShops.some(
              (shop) => String(shop.id) === String(selected.analyticsShopId),
            )}
            onToggleShopFollow={() =>
              toggleShopFollow({ id: selected.analyticsShopId || selected.shopId, name: selected.shop })
            }
            onAdd={(quantity, variants) => {
              void updateSharedCart(selected.id, quantity, variants);
              toast("已加入购物袋");
            }}
            onBuy={(quantity, variants) => {
              void (async () => {
                await updateSharedCart(selected.id, quantity, variants);
                show("checkout");
              })();
            }}
            onContact={async () => {
              if (isGuest || !selected.analyticsShopId) {
                toast("请登录后联系店主");
                return;
              }
              const response = await fetch(`${API_BASE}/api/messages/buyer`, {
                method: "POST",
                credentials: "include",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ shopId: selected.analyticsShopId, content: `想咨询作品：${selected.title}` }),
              });
              if (!response.ok) return toast("咨询发送失败");
              show("messages");
            }}
            onReport={async (reason, detail, evidence) => {
              if (isGuest || !selected.catalogId) {
                toast("请登录后提交举报");
                return false;
              }
              const response = await fetch(`${API_BASE}/api/reports`, {
                method: "POST",
                credentials: "include",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ targetType: "product", targetId: selected.catalogId, reason, detail, evidence }),
              });
              const payload = (await response.json()) as { error?: string };
              if (!response.ok) {
                toast(payload.error || "举报提交失败");
                return false;
              }
              toast("举报已提交，平台将尽快处理");
              return true;
            }}
          />
        )}
        {account.role === "seller" && view === "shop" && (
          <ShopPage
            shop={data.shop}
            products={data.products.filter(
              (p) => p.shopId === 99 && p.listed !== false,
            )}
            onOpen={openProduct}
            onStudio={() => show("studio")}
          />
        )}
        {account.role === "buyer" && view === "cart" && (
          <Cart
            data={data}
            onUpdate={(id, quantity, variants = {}) => void updateSharedCart(id, quantity, variants)}
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
                method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify(address),
              });
              const payload = (await response.json()) as { address?: BuyerAddress; error?: string };
              if (!response.ok) throw new Error(payload.error || "地址保存失败");
              setAddresses((items) => [payload.address!, ...items.map((item) => ({ ...item, isDefault: false }))]);
              return payload.address!;
            }}
            onBack={() => show("cart")}
            onFinish={async (paymentMethod, addressId) => {
              const created = await createSharedOrders(addressId, paymentMethod);
              if (!created?.length) return;
              const results = await Promise.all(created.map((order) => paySharedOrder(order.id, paymentMethod)));
              if (results.every(Boolean)) toast("支付成功，订单已进入待发货");
              else toast("订单已创建，可在订单中心继续支付");
              show("orders");
            }}
          />
        )}
        {account.role === "buyer" && view === "coupons" && <main className="container page section"><div className="page-title"><div><h1>领券中心</h1><p>领取后会存入优惠券包，结算时自动使用最优优惠。</p></div></div><section className="coupon-grid">{claimableCoupons.map((coupon) => <article key={coupon.id}><b>{coupon.name}</b><strong>满 {money(coupon.threshold)} 减 {money(coupon.discount)}</strong><small>每人最多领取 {coupon.claimLimit} 次</small><button className="primary" onClick={async () => { const response = await fetch(`${API_BASE}/api/campaigns/${coupon.id}/claim`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: "{}" }); if (response.ok) { const payload = (await response.json()) as { coupons: typeof coupons }; setCoupons(payload.coupons); await refreshCoupons(); toast("优惠券已领取"); } else toast("领取失败或已达到上限"); }}>立即领取</button></article>)}{!claimableCoupons.length && <p>暂无可领取的优惠券。</p>}</section><section className="studio-panel coupon-wallet"><div className="panel-head"><h2>优惠券包</h2><span>{coupons.filter((coupon) => coupon.available).length} 张可用</span></div>{coupons.map((coupon) => <article key={coupon.id}><span><b>{coupon.name}</b><small>满 {money(coupon.threshold)} 减 {money(coupon.discount)} · 剩余 {coupon.remaining} 次</small></span><strong className={coupon.available ? "coupon-active" : ""}>{coupon.available ? "可使用" : "已用完或失效"}</strong></article>)}{!coupons.length && <p>尚未领取优惠券。</p>}</section></main>}
        {account.role === "buyer" && view === "orders" && (
          <Orders
            data={data}
            orders={sharedOrders}
            afterSales={sharedAfterSales}
            reviews={sharedReviews}
            onShipping={(id) => {
              setShippingId(id);
              setShippingModalOpen(true);
            }}
            onReceive={async (id) => {
              if (await updateSharedOrder(id, "receive")) toast("已确认收货");
            }}
            onCancel={async (id) => {
              if (await updateSharedOrder(id, "cancel")) toast("订单已取消，库存已回补");
            }}
            onPay={paySharedOrder}
            onReview={createReview}
            onFollowup={createReviewFollowup}
            onAfterSale={createAfterSale}
            onReturnShipment={submitReturnShipment}
          />
        )}
        {account.role === "buyer" && view === "following" && (
          <FollowingShops
            shops={data.followedShops}
            onDiscover={() => show("discover")}
            onUnfollow={toggleShopFollow}
          />
        )}
        {account.role === "buyer" && view === "favorites" && (
          <FavoritesPage
            products={data.products.filter((product) => product.listed !== false)}
            favorites={data.favorites}
            onOpen={openProduct}
            onFavorite={toggleFavorite}
            onDiscover={() => show("discover")}
          />
        )}
        {view === "messages" && (
          <Messages role="buyer" />
        )}
        {view === "notifications" && (
          <NotificationCenter
            notifications={notifications}
            onRead={async (ids) => {
              await fetch(`${API_BASE}/api/notifications/read`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ids }) });
              setNotifications((items) => items.map((item) => ids.includes(item.id) ? { ...item, read: true } : item));
              setNotificationUnread((value) => Math.max(0, value - ids.length));
            }}
            onReadAll={async () => {
              await fetch(`${API_BASE}/api/notifications/read`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: "{}" });
              setNotifications((items) => items.map((item) => ({ ...item, read: true })));
              setNotificationUnread(0);
            }}
            onOpen={(item) => {
              if (item.relatedType === "product") {
                const product = data.products.find((value) => value.catalogId === item.relatedId);
                if (product) return openProduct(product.id);
              }
              if (item.relatedType === "shop") return show("messages");
              show("orders");
            }}
          />
        )}
        {!isGuest && view === "security" && (
          <AccountSecurity account={account} onBack={() => show(account.role === "seller" ? "studio" : "home")} />
        )}
        {!isGuest && view === "profile" && (
          <ProfileSettings
            account={account}
            onBack={() => show(account.role === "seller" ? "studio" : "home")}
            onSecurity={() => show("security")}
            onFavorites={() => show("favorites")}
            onOrders={() => show("orders")}
            onCoupons={() => { void refreshCoupons(); show("coupons"); }}
            onFollowing={() => show("following")}
            onAccountUpdated={onAccountUpdated}
            onAccountDeleted={onAccountDeleted}
          />
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
        <ShippingModal
          order={sharedOrders.find((order) => order.id === shippingId)}
          onClose={() => { setShippingModalOpen(false); setShippingId(""); }}
        />
      )}
      {!(account.role === "seller" && view === "studio") && (
        <PlatformFooter onReset={reset} onNotice={toast} />
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
  onReset,
  onNotice,
}: {
  className?: string;
  onReset: () => void;
  onNotice: (message: string) => void;
}) {
  return (
    <footer className={className}>
      <div className="container footer-inner">
        <div className="footer-brand">
          <strong>手作集</strong>
          <span>让每一件认真做的东西，被认真看见。</span>
        </div>
        <nav className="footer-links" aria-label="平台服务">
          {["关于平台", "入驻须知", "售后规则", "帮助中心"].map((label) => (
            <button key={label} onClick={() => onNotice(`${label}内容即将上线`)}>
              {label}
            </button>
          ))}
        </nav>
        <button className="footer-reset" onClick={onReset}>
          <Settings2 size={15} />
          恢复初始数据
        </button>
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
}: {
  products: Product[];
  favorites: number[];
  onOpen: (id: number) => void;
  onFavorite: (id: number) => void;
  onCategory: (c: Category) => void;
}) {
  return (
    <>
      <section className="hero">
        <div className="hero-image" />
        <div className="hero-copy container">
          <p>HANDMADE, ORIGINAL, YOURS</p>
          <h1>
            把喜欢的生活
            <br />
            带回家
          </h1>
          <span>从一件有温度的手作开始，遇见认真生活的人。</span>
          <button className="primary" onClick={() => onCategory("陶艺")}>
            去逛逛 <ChevronRight size={18} />
          </button>
        </div>
      </section>
      <section className="container section">
        <div className="section-heading">
          <div>
            <p className="eyebrow">为你精选</p>
            <h2>发现手作的各种可能</h2>
          </div>
          <button className="text-link" onClick={() => onCategory("陶艺")}>
            查看全部 <ChevronRight size={17} />
          </button>
        </div>
        <div className="category-grid">
          {categories.map((c) => (
            <button
              className="category-tile"
              onClick={() => onCategory(c.name)}
              key={c.name}
            >
              <img src={c.image} alt="" />
              <span>{c.name}</span>
              <small>{c.caption}</small>
            </button>
          ))}
        </div>
      </section>
      <section className="warm-section">
        <div className="container section">
          <div className="section-heading">
            <div>
              <p className="eyebrow">THIS WEEK'S FINDS</p>
              <h2>本周新上架</h2>
            </div>
            <button className="text-link" onClick={() => onCategory("陶艺")}>
              发现更多 <ChevronRight size={17} />
            </button>
          </div>
          <ProductGrid
            products={products.slice(0, 6)}
            favorites={favorites}
            onOpen={onOpen}
            onFavorite={onFavorite}
          />
        </div>
      </section>
      <ActivityShowcase />
      <section className="maker-band">
        <div className="container maker-content">
          <div>
            <p className="eyebrow">MAKE YOUR SPACE</p>
            <h2>你的创意，也值得拥有一家店</h2>
            <p>从作品展示到订单管理，轻松开启个人手作事业。</p>
            <button className="outline-light">
              开始开店 <ChevronRight size={18} />
            </button>
          </div>
          <div className="maker-stat">
            <strong>12,840</strong>
            <span>位独立创作者正在这里分享作品</span>
          </div>
        </div>
      </section>
    </>
  );
}

function ActivityShowcase() {
  type Activity = { id: string; name: string; description: string; endsAt?: string; page: { banner?: string; theme?: { accent?: string }; modules?: string[] }; products: { id: string; title: string; shop: string; image?: string; availableStock: number }[] };
  const [activities, setActivities] = useState<Activity[]>([]);
  useEffect(() => { fetch(`${API_BASE}/api/activities`).then((response) => response.ok ? response.json() : Promise.reject()).then((payload: { activities?: Activity[] }) => setActivities(payload.activities || [])).catch(() => undefined); }, []);
  if (!activities.length) return null;
  return <section className="container section activity-showcase">{activities.slice(0, 2).map((activity) => <article key={activity.id} style={{ borderColor: activity.page.theme?.accent || "#e66020" }}><div className="activity-showcase-banner" style={activity.page.banner ? { backgroundImage: `url(${activity.page.banner})` } : { backgroundColor: activity.page.theme?.accent || "#e66020" }}><span>{activity.page.modules?.join(" · ") || "精选活动"}</span><h2>{activity.name}</h2><p>{activity.description}</p>{activity.endsAt && <small>截至 {activity.endsAt}</small>}</div><div className="activity-showcase-products">{activity.products.slice(0, 4).map((product) => <div key={product.id}>{product.image && <img src={product.image} alt={product.title} />}<b>{product.title}</b><small>{product.shop} · 剩余 {product.availableStock}</small></div>)}</div></article>)}</section>;
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
}: {
  products: Product[];
  personalizedProducts?: Product[];
  query: string;
  searchMeta?: { originalQuery: string; corrected?: string | null; recommendations: string[]; zeroResult?: { message: string; productId?: string | null } | null };
  serverFiltered?: boolean;
  category: Category | "全部";
  sort: "relevance" | "latest" | "price_asc" | "price_desc" | "sales";
  favorites: number[];
  onOpen: (id: number) => void;
  onFavorite: (id: number) => void;
  onCategory: (c: Category | "全部") => void;
  onSort: (sort: "relevance" | "latest" | "price_asc" | "price_desc" | "sales") => void;
  onQueryChange?: (query: string) => void;
}) {
  const filtered = products.filter(
    (p) =>
      (category === "全部" || p.category === category) &&
      (serverFiltered || !query || `${p.title}${p.shop}${p.tags.join("")}${p.seoTags?.join("") || ""}`.includes(query)),
  );
  return (
    <div className="container page section">
      <div className="breadcrumbs">
        首页 <ChevronRight size={14} /> 发现好物
      </div>
      <div className="discover-heading">
        <div>
          <h1>
            {query
              ? `“${query}” 的搜索结果`
              : category === "全部"
                ? "发现好物"
                : category}
          </h1>
          <p>{filtered.length} 件来自独立创作者的作品</p>
        </div>
        <label className="search-sort"><SlidersHorizontal size={17} /><select value={sort} onChange={(event) => onSort(event.target.value as typeof sort)}><option value="relevance">相关度</option><option value="latest">最新发布</option><option value="sales">销量优先</option><option value="price_asc">价格从低到高</option><option value="price_desc">价格从高到低</option></select></label>
      </div>
      {(searchMeta.corrected || searchMeta.recommendations.length > 0 || searchMeta.zeroResult) && <section className="search-guidance">
        {searchMeta.corrected && <p>已按“{searchMeta.corrected}”为你查找相关作品。</p>}
        {searchMeta.zeroResult && <p className="search-zero-result">{searchMeta.zeroResult.message}</p>}
        {searchMeta.recommendations.length > 0 && <div><span>相关搜索</span>{searchMeta.recommendations.map((item) => <button key={item} onClick={() => onQueryChange(item)}>{item}</button>)}</div>}
      </section>}
      {!query && category === "全部" && personalizedProducts.length > 0 && <section className="personalized-products">
        <div className="section-heading"><div><h2>猜你喜欢</h2><p>根据浏览、收藏、加购和购买记录推荐</p></div></div>
        <ProductGrid products={personalizedProducts} favorites={favorites} onOpen={onOpen} onFavorite={onFavorite} />
      </section>}
      <div className="discover-layout">
        <aside>
          <strong>分类</strong>
          {(
            ["全部", ...categories.map((c) => c.name)] as (Category | "全部")[]
          ).map((c) => (
            <button
              key={c}
              className={c === category ? "selected" : ""}
              onClick={() => onCategory(c)}
            >
              {c}
            </button>
          ))}
          <hr />
          <strong>价格区间</strong>
          <label>
            <input type="checkbox" /> ¥0 - ¥100
          </label>
          <label>
            <input type="checkbox" /> ¥100 - ¥300
          </label>
          <label>
            <input type="checkbox" /> ¥300 以上
          </label>
          <hr />
          <strong>商品特性</strong>
          <label>
            <input type="checkbox" /> 可定制
          </label>
          <label>
            <input type="checkbox" /> 现货
          </label>
        </aside>
        <ProductGrid
          products={filtered}
          favorites={favorites}
          onOpen={onOpen}
          onFavorite={onFavorite}
        />
      </div>
    </div>
  );
}

function ProductGrid({
  products,
  favorites,
  onOpen,
  onFavorite,
}: {
  products: Product[];
  favorites: number[];
  onOpen: (id: number) => void;
  onFavorite: (id: number) => void;
}) {
  return (
    <div className="product-grid">
      {products.map((p) => (
        <article className="product-card" data-testid={`product-card-${p.catalogId || p.id}`} key={p.id}>
          <div className="product-image" onClick={() => onOpen(p.id)}>
            <img src={p.image} alt={p.title} />
            {p.custom && <span className="custom-badge">可定制</span>}
            <IconButton
              icon={Heart}
              label="收藏"
              active={favorites.includes(p.id)}
              onClick={(event) => {
                event.stopPropagation();
                onFavorite(p.id);
              }}
            />
          </div>
          <button data-testid={`product-open-${p.catalogId || p.id}`} className="product-info" onClick={() => onOpen(p.id)}>
            <h3>{p.title}</h3>
            <p>{p.shop}</p>
            <span className="rating">
              <Star size={14} fill="currentColor" />
              {p.rating} <small>({p.reviews})</small>
            </span>
            <strong>{money(p.price)}</strong>
            {p.oldPrice && <del>{money(p.oldPrice)}</del>}
          </button>
        </article>
      ))}
    </div>
  );
}

function ProductDetail({
  product,
  favorite,
  onBack,
  onFavorite,
  shopFollowed,
  onToggleShopFollow,
  onAdd,
  onBuy,
  onContact,
  onReport,
}: {
  product: Product;
  favorite: boolean;
  onBack: () => void;
  onFavorite: (id: number) => void;
  shopFollowed: boolean;
  onToggleShopFollow: () => void;
  onAdd: (q: number, variants: Record<string, string>) => void;
  onBuy: (q: number, variants: Record<string, string>) => void;
  onContact: () => void;
  onReport: (reason: string, detail: string, evidence: string[]) => Promise<boolean>;
}) {
  const [quantity, setQuantity] = useState(1);
  const [note, setNote] = useState("");
  const [showReport, setShowReport] = useState(false);
  const [reportReason, setReportReason] = useState("涉嫌违法违规");
  const [reportDetail, setReportDetail] = useState("");
  const [reportEvidence, setReportEvidence] = useState<string[]>([]);
  const addReportEvidence = (file?: File) => {
    if (!file || reportEvidence.length >= 6) return;
    const reader = new FileReader();
    reader.onload = async () => {
      const response = await fetch(`${API_BASE}/api/media`, {
        method: "POST", credentials: "include", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ data: String(reader.result), mediaType: "image" }),
      });
      const payload = (await response.json()) as { url?: string };
      if (response.ok && payload.url) setReportEvidence((items) => [...items, payload.url!]);
    };
    reader.readAsDataURL(file);
  };
  const [productReviews, setProductReviews] = useState<ProductReview[]>([]);
  const gallery = product.images?.length ? product.images : [product.image];
  const [activeImage, setActiveImage] = useState(gallery[0]);
  const [selectedVariants, setSelectedVariants] = useState<
    Record<string, string>
  >(() =>
    Object.fromEntries(
      (product.variants || []).map((variant) => [
        variant.name,
        variant.values[0],
      ]),
    ),
  );
  useEffect(() => setActiveImage(gallery[0]), [product.id]);
  useEffect(
    () =>
      setSelectedVariants(
        product.skus?.find((sku) => (sku.status ?? "active") === "active" && sku.stock > 0)?.optionValues ||
          Object.fromEntries(
            (product.variants || []).map((variant) => [
              variant.name,
              variant.values[0],
            ]),
          ),
      ),
    [product.id],
  );
  useEffect(() => {
    if (!product.catalogId) {
      setProductReviews([]);
      return;
    }
    let active = true;
    fetch(`${API_BASE}/api/catalog/products/${encodeURIComponent(product.catalogId)}/reviews`)
      .then((response) => (response.ok ? response.json() : Promise.reject()))
      .then((payload: { reviews: ProductReview[] }) => {
        if (active) setProductReviews(payload.reviews);
      })
      .catch(() => {
        if (active) setProductReviews([]);
      });
    return () => {
      active = false;
    };
  }, [product.catalogId]);
  const selectedSku = product.skus?.find((sku) =>
    Object.entries(selectedVariants).every(
      ([name, value]) => sku.optionValues[name] === value,
    ),
  );
  const availableStock = selectedSku && (selectedSku.status ?? "active") === "active" ? selectedSku.stock : product.skus?.length ? 0 : product.stock;
  const displayPrice = selectedSku?.price ?? product.price;
  const rating = productReviews.length
    ? productReviews.reduce((total, review) => total + review.rating, 0) / productReviews.length
    : product.rating;
  const reviewCount = productReviews.length || product.reviews;
  const isVariantValueAvailable = (name: string, value: string) => {
    if (!product.skus?.length) return true;
    const nextSelection = { ...selectedVariants, [name]: value };
    return product.skus.some(
      (sku) =>
        (sku.status ?? "active") === "active" &&
        sku.stock > 0 &&
        Object.entries(nextSelection).every(
          ([optionName, optionValue]) =>
            sku.optionValues[optionName] === optionValue,
        ),
    );
  };
  useEffect(() => {
    setQuantity((current) => Math.max(1, Math.min(current, availableStock || 1)));
  }, [availableStock, product.id]);
  return (
    <div className="container page section">
      <button className="back" onClick={onBack}>
        <ArrowLeft size={18} />
        返回商品列表
      </button>
      <div className="detail-layout">
        <div className="detail-media">
          <div className="detail-image">
            <img src={activeImage} alt={product.title} />
          </div>
          {gallery.length > 1 && (
            <div className="detail-gallery">
              {gallery.map((image, index) => (
                <button
                  className={image === activeImage ? "active" : ""}
                  onClick={() => setActiveImage(image)}
                  key={image}
                >
                  <img src={image} alt={`${product.title} 图片 ${index + 1}`} />
                </button>
              ))}
            </div>
          )}
          {product.video && (
            <video
              className="detail-video"
              src={product.video}
              controls
              preload="metadata"
            />
          )}
        </div>
        <div className="detail-info">
          <p className="eyebrow">
            {product.category} · {product.shop}
          </p>
          <h1>{product.title}</h1>
          <div className="detail-rating">
            <Star size={17} fill="currentColor" />
            {rating.toFixed(1)} <u>{reviewCount} 条评价</u>
          </div>
          <h2>{money(displayPrice)}</h2>
          <p className="stock">
            {availableStock > 0 ? `现货 ${availableStock} 件 · 预计 2-4 天发货` : "该规格组合已售罄"}
          </p>
          {product.variants?.map((variant) => (
            <div className="variant-group" key={variant.name}>
              <span className="label">{variant.name}</span>
              <div>
                {variant.values.map((value) => (
                  <button
                    className={
                      `${selectedVariants[variant.name] === value ? "selected" : ""} ${
                        isVariantValueAvailable(variant.name, value) ? "" : "sold-out"
                      }`
                    }
                    key={value}
                    disabled={!isVariantValueAvailable(variant.name, value)}
                    onClick={() => {
                      setSelectedVariants((current) => ({
                        ...current,
                        [variant.name]: value,
                      }));
                      const variantImage = variant.valueImages?.[value];
                      if (variantImage) setActiveImage(variantImage);
                    }}
                  >
                    {variant.valueImages?.[value] ? (
                      <img className="variant-value-image" src={variant.valueImages[value]} alt="" />
                    ) : variant.name.includes("颜色") && (
                      <i style={{ backgroundColor: swatchColor(value) }} />
                    )}
                    {value}
                  </button>
                ))}
              </div>
            </div>
          ))}
          {product.custom && (
            <>
              <label className="label" htmlFor="note">
                定制说明（可选）
              </label>
              <textarea
                id="note"
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder="例如：刻字内容、希望的颜色..."
              />
            </>
          )}
          <div className="quantity-row">
            <span>数量</span>
            <div>
              <IconButton
                icon={Minus}
                label="减少数量"
                onClick={() => setQuantity(Math.max(1, quantity - 1))}
              />
              <b>{quantity}</b>
              <IconButton
                icon={Plus}
                label="增加数量"
                onClick={() =>
                  setQuantity(Math.min(availableStock, quantity + 1))
                }
              />
            </div>
          </div>
          <div className="buy-row">
            <button
              data-testid="product-buy-now"
              className="primary grow"
              disabled={availableStock <= 0}
              onClick={() => onBuy(quantity, selectedVariants)}
            >
              立即购买
            </button>
            <button
              data-testid="product-add-cart"
              className="secondary grow"
              disabled={availableStock <= 0}
              onClick={() => onAdd(quantity, selectedVariants)}
            >
              <ShoppingBag size={18} />
              加入购物袋
            </button>
            <IconButton
              icon={Heart}
              active={favorite}
              label="收藏"
              onClick={() => onFavorite(product.id)}
            />
          </div>
          <div className="shop-mini">
            <Store size={22} />
            <div>
              <strong>{product.shop}</strong>
              <span>独立创作者 · 已售 300+ 件</span>
            </div>
            <button className="text-link" onClick={onToggleShopFollow}>
              {shopFollowed ? "已关注" : "关注店铺"}
            </button>
            <button className="text-link" onClick={onContact}>咨询店主</button>
          </div>
          <div className="content-report">
            <button className="text-link" type="button" onClick={() => setShowReport((value) => !value)}>
              举报作品
            </button>
            {showReport && (
              <div className="report-form">
                <select value={reportReason} onChange={(event) => setReportReason(event.target.value)}>
                  <option>涉嫌违法违规</option>
                  <option>侵权或仿冒</option>
                  <option>虚假宣传</option>
                  <option>不当内容</option>
                </select>
                <textarea value={reportDetail} maxLength={200} placeholder="补充举报说明（可选）" onChange={(event) => setReportDetail(event.target.value)} />
                <label>
                  上传证据（最多 6 张）
                  <input type="file" accept="image/jpeg,image/png,image/webp" onChange={(event) => { addReportEvidence(event.target.files?.[0]); event.currentTarget.value = ""; }} />
                </label>
                {reportEvidence.length > 0 && <small>已上传 {reportEvidence.length} 张证据</small>}
                <button
                  className="secondary"
                  type="button"
                  onClick={() => {
                    void onReport(reportReason, reportDetail, reportEvidence).then((submitted) => {
                      if (submitted) {
                        setShowReport(false);
                        setReportDetail("");
                        setReportEvidence([]);
                      }
                    });
                  }}
                >
                  提交举报
                </button>
              </div>
            )}
          </div>
          <div className="line" />
          <p className="label">关于这件作品</p>
          <p>{product.description}</p>
          <p className="label">材质</p>
          <p>{product.material}</p>
        </div>
      </div>
      <section className="product-reviews">
        <div className="section-heading">
          <h2>买家评价</h2>
          <span>{reviewCount} 条</span>
        </div>
        {productReviews.length ? (
          <div className="product-review-list">
            {productReviews.map((review) => (
              <article key={review.id}>
                <header>
                  <b>{review.buyerName || "匿名买家"}</b>
                  <span>{review.createdAt}</span>
                </header>
                <div className="product-review-stars" aria-label={`${review.rating} 星评价`}>
                  {Array.from({ length: 5 }, (_, index) => (
                    <Star key={index} size={15} fill={index < review.rating ? "currentColor" : "none"} />
                  ))}
                </div>
                <p>{review.content}</p>
                {!!review.images?.length && <div className="review-images">{review.images.map((image) => <img key={image} src={image} alt="买家评价图片" />)}</div>}
                {review.followup && <p className="review-followup">追评：{review.followup}</p>}
                {review.sellerReply && <p className="seller-review-reply">店主回复：{review.sellerReply}</p>}
              </article>
            ))}
          </div>
        ) : (
          <p className="product-review-empty">暂无真实评价</p>
        )}
      </section>
    </div>
  );
}

function NotificationCenter({ notifications, onRead, onReadAll, onOpen }: {
  notifications: NotificationItem[];
  onRead: (ids: string[]) => void;
  onReadAll: () => void;
  onOpen: (item: NotificationItem) => void;
}) {
  const [filter, setFilter] = useState<"all" | "unread" | "orders" | "after_sale" | "governance">("all");
  const visible = notifications.filter((item) => filter === "all" || (filter === "unread" && !item.read) || (filter === "orders" && ["order_paid", "order_shipped", "order_completed", "review_reminder"].includes(item.type)) || (filter === "after_sale" && item.type.includes("sale") || item.type.includes("refund") || item.type.includes("return")) || (filter === "governance" && ["report_result", "appeal_result", "enforcement"].includes(item.type)));
  return <div className="container page section"><div className="page-title"><div><h1>通知中心</h1><p>查看订单、售后与平台动态</p></div><button className="secondary" onClick={onReadAll}>全部已读</button></div><div className="order-filters">{[["all","全部"],["unread","未读"],["orders","订单"],["after_sale","售后"],["governance","平台"]].map(([id,label]) => <button key={id} className={filter === id ? "selected" : ""} onClick={() => setFilter(id as typeof filter)}>{label}</button>)}</div><section className="messages-panel">{visible.map((item) => <button className={`message-item ${item.read ? "" : "unread"}`} key={item.id} onClick={() => { if (!item.read) onRead([item.id]); onOpen(item); }}><b>{item.title}</b><span>{item.content}</span><small>{item.createdAt}</small></button>)}{!visible.length && <p>暂无通知。</p>}</section></div>;
}

function Messages({ role, embedded = false }: { role: "buyer" | "seller"; embedded?: boolean }) {
  type Conversation = { shopId: string; shop: string; buyerUserId?: string; buyer?: string; preview: string; lastMessageAt: string; unread: number };
  type SyncedShopMessage = ShopMessage & { cursor?: number };
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [selectedKey, setSelectedKey] = useState("");
  const [messages, setMessages] = useState<SyncedShopMessage[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);
  const [quickReplies, setQuickReplies] = useState<{ id: string; content: string; category: string }[]>([]);
  const [content, setContent] = useState("");
  const [search, setSearch] = useState("");
  const [selectedOrderId, setSelectedOrderId] = useState("");
  const [newReply, setNewReply] = useState("");
  const [replyCategory, setReplyCategory] = useState("general");
  const [notice, setNotice] = useState("");
  const messageCursor = useRef(0);

  const endpoint = role === "buyer" ? "/api/messages/buyer" : "/api/messages/seller";
  const conversationKey = (item: Conversation) => `${item.shopId}:${item.buyerUserId || "buyer"}`;
  const selected = conversations.find((item) => conversationKey(item) === selectedKey);

  const loadConversations = async (keepSelection = true) => {
    const query = search.trim() ? `?q=${encodeURIComponent(search.trim())}` : "";
    const response = await fetch(`${API_BASE}${endpoint}${query}`, { credentials: "include" });
    const payload = await response.json().catch(() => ({})) as { conversations?: Conversation[]; error?: string };
    if (!response.ok) throw new Error(payload.error || "消息加载失败");
    const next = payload.conversations || [];
    setConversations(next);
    if (!keepSelection || !next.some((item) => conversationKey(item) === selectedKey)) {
      setMessages([]);
      messageCursor.current = 0;
      setSelectedKey(next[0] ? conversationKey(next[0]) : "");
    }
  };

  const openConversation = async (item: Conversation) => {
    setSelectedKey(conversationKey(item));
    setMessages([]);
    messageCursor.current = 0;
    setNotice("");
    const params = new URLSearchParams({ shopId: item.shopId });
    if (role === "seller" && item.buyerUserId) params.set("buyerUserId", item.buyerUserId);
    const response = await fetch(`${API_BASE}${endpoint}?${params.toString()}`, { credentials: "include" });
    const payload = await response.json().catch(() => ({})) as { messages?: SyncedShopMessage[]; error?: string };
    if (!response.ok) return setNotice(payload.error || "会话加载失败");
    const nextMessages = payload.messages || [];
    messageCursor.current = nextMessages[nextMessages.length - 1]?.cursor || 0;
    setMessages(nextMessages);
    void loadConversations();
  };

  useEffect(() => {
    void loadConversations(false).catch((error: Error) => setNotice(error.message));
    fetch(`${API_BASE}${role === "buyer" ? "/api/orders" : "/api/orders/seller"}`, { credentials: "include" })
      .then((response) => response.ok ? response.json() : Promise.reject())
      .then((payload: { orders?: Order[] }) => setOrders(payload.orders || []))
      .catch(() => undefined);
    if (role === "seller") {
      fetch(`${API_BASE}/api/messages/quick-replies`, { credentials: "include" })
        .then((response) => response.ok ? response.json() : Promise.reject())
        .then((payload: { quickReplies?: { id: string; content: string; category: string }[] }) => setQuickReplies(payload.quickReplies || []))
        .catch(() => undefined);
    }
  }, [role]);

  useEffect(() => {
    const timer = window.setTimeout(() => { void loadConversations(false).catch((error: Error) => setNotice(error.message)); }, 220);
    return () => window.clearTimeout(timer);
  }, [search]);

  useEffect(() => {
    if (!selected || messages.length) return;
    void openConversation(selected);
  }, [selectedKey, conversations]);

  useEffect(() => {
    if (!selected) return;
    const params = new URLSearchParams({ shopId: selected.shopId, after: String(messageCursor.current) });
    if (role === "seller" && selected.buyerUserId) params.set("buyerUserId", selected.buyerUserId);
    const updatesEndpoint = `${endpoint}/updates`;
    let active = true;
    const poll = async () => {
      try {
        params.set("after", String(messageCursor.current));
        const response = await fetch(`${API_BASE}${updatesEndpoint}?${params.toString()}`, { credentials: "include" });
        const payload = await response.json().catch(() => ({})) as { messages?: SyncedShopMessage[]; cursor?: number; error?: string };
        if (!response.ok) throw new Error(payload.error || "Message sync failed");
        const incoming = payload.messages || [];
        if (!active || !incoming.length) return;
        messageCursor.current = payload.cursor || incoming[incoming.length - 1]?.cursor || messageCursor.current;
        setMessages((current) => {
          const existing = new Set(current.map((message) => message.id));
          return [...current, ...incoming.filter((message) => !existing.has(message.id))];
        });
        void loadConversations();
      } catch (error) {
        if (active) setNotice(error instanceof Error ? error.message : "Message sync failed");
      }
    };
    const timer = window.setInterval(() => { void poll(); }, 4000);
    return () => { active = false; window.clearInterval(timer); };
  }, [endpoint, role, selectedKey]);

  const sendMessage = async (payload: { type: "text" | "image" | "order"; content?: string; attachmentUrl?: string; orderId?: string }) => {
    if (!selected) return setNotice("请先选择一个会话");
    const body = role === "buyer"
      ? { shopId: selected.shopId, ...payload }
      : { shopId: selected.shopId, buyerUserId: selected.buyerUserId, ...payload };
    const response = await fetch(`${API_BASE}${endpoint}`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    const result = await response.json().catch(() => ({})) as { error?: string };
    if (!response.ok) return setNotice(result.error || "消息发送失败");
    setContent("");
    setSelectedOrderId("");
    await openConversation(selected);
  };

  const uploadImage = async (file: File) => {
    const data = await new Promise<string>((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result));
      reader.onerror = () => reject(new Error("图片读取失败"));
      reader.readAsDataURL(file);
    });
    const response = await fetch(`${API_BASE}/api/media`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ data, mediaType: "image" }) });
    const payload = await response.json().catch(() => ({})) as { url?: string; error?: string };
    if (!response.ok || !payload.url) throw new Error(payload.error || "图片上传失败");
    await sendMessage({ type: "image", attachmentUrl: payload.url });
  };

  const matchingOrders = orders.filter((order) => !!selected && String(order.shopId) === String(selected.shopId) && (role === "buyer" || order.buyerUserId === selected.buyerUserId));
  const visibleConversations = conversations.filter((item) => `${item.shop} ${item.buyer || ""} ${item.preview}`.toLowerCase().includes(search.trim().toLowerCase()));
  const shellClass = embedded ? "conversation-center conversation-embedded" : "container page section conversation-center";
  return <div className={shellClass}>
    {!embedded && <div className="page-title"><div><h1>消息</h1><p>查看会话、订单咨询与服务回复</p></div></div>}
    {notice && <p className="auth-error">{notice}</p>}
    <section className="conversation-layout">
      <aside className="conversation-sidebar">
        <div className="conversation-search"><Search size={16} /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="搜索会话或消息" /></div>
        <div className="conversation-list">
          {visibleConversations.map((item) => <button key={conversationKey(item)} className={conversationKey(item) === selectedKey ? "selected" : ""} onClick={() => void openConversation(item)}><b>{role === "seller" ? item.buyer || "买家" : item.shop}</b><span>{item.preview}</span><small>{item.lastMessageAt}</small>{item.unread > 0 && <i>{item.unread > 99 ? "99+" : item.unread}</i>}</button>)}
          {!visibleConversations.length && <p>暂无匹配会话</p>}
        </div>
      </aside>
      <div className="conversation-detail">
        {selected ? <>
          <header><div><b>{role === "seller" ? selected.buyer || "买家" : selected.shop}</b><small>{role === "seller" ? selected.shop : "店铺会话"}</small></div></header>
          <div className="conversation-messages">
            {messages.map((message) => <article className={(role === "buyer" ? message.sender === "buyer" : message.sender === "seller") ? "outgoing" : "incoming"} key={message.id}>
              {message.type === "image" ? <img src={message.attachmentUrl} alt="聊天图片" /> : message.type === "order" && message.order ? <div className="message-order-card">{message.order.image && <img src={message.order.image} alt="订单作品" />}<span><b>{message.order.title}</b><small>订单 {message.order.orderNo || message.order.id} · {message.order.status}</small><strong>￥{message.order.amount?.toFixed(2)}</strong></span></div> : <p>{message.content}</p>}
              <small>{message.createdAt}</small>
            </article>)}
            {!messages.length && <p className="conversation-empty">选择会话后查看沟通记录</p>}
          </div>
          {role === "seller" && <div className="quick-replies"><div>{quickReplies.map((reply) => <span key={reply.id}><button type="button" onClick={() => setContent(reply.content)}>{reply.category} · {reply.content}</button><button type="button" className="remove" title="删除快捷回复" onClick={async () => { const response = await fetch(`${API_BASE}/api/messages/quick-replies/${encodeURIComponent(reply.id)}`, { method: "DELETE", credentials: "include" }); if (!response.ok) return setNotice("删除快捷回复失败"); setQuickReplies((items) => items.filter((item) => item.id !== reply.id)); }}>×</button></span>)}</div><form onSubmit={async (event) => { event.preventDefault(); if (!newReply.trim()) return; const response = await fetch(`${API_BASE}/api/messages/quick-replies`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ content: newReply.trim(), category: replyCategory }) }); const payload = await response.json().catch(() => ({})) as { quickReply?: { id: string; content: string; category: string }; error?: string }; if (!response.ok || !payload.quickReply) return setNotice(payload.error || "快捷回复保存失败"); setQuickReplies((items) => [payload.quickReply!, ...items]); setNewReply(""); }}><input value={newReply} onChange={(event) => setNewReply(event.target.value)} maxLength={500} placeholder="新增快捷回复" /><input value={replyCategory} onChange={(event) => setReplyCategory(event.target.value)} maxLength={30} placeholder="分类" /><button className="secondary">保存</button></form></div>}
          <div className="conversation-tools"><label className="icon-upload" title="发送图片"><ImagePlus size={18} /><input type="file" accept="image/jpeg,image/png,image/webp" onChange={(event) => { const file = event.target.files?.[0]; event.currentTarget.value = ""; if (file) void uploadImage(file).catch((error: Error) => setNotice(error.message)); }} /></label><select value={selectedOrderId} onChange={(event) => setSelectedOrderId(event.target.value)}><option value="">发送订单卡片</option>{matchingOrders.map((order) => <option value={order.orderId || order.id} key={order.orderId || order.id}>订单 {order.id} · ￥{order.amount.toFixed(2)}</option>)}</select><button className="secondary" type="button" disabled={!selectedOrderId} onClick={() => void sendMessage({ type: "order", orderId: selectedOrderId })}>发送订单</button></div>
          <form className="conversation-composer" onSubmit={(event) => { event.preventDefault(); if (content.trim()) void sendMessage({ type: "text", content: content.trim() }); }}><input value={content} onChange={(event) => setContent(event.target.value)} maxLength={500} placeholder="输入消息" /><button className="primary">发送</button></form>
        </> : <div className="conversation-empty">暂时没有会话。请从作品或订单中联系店铺。</div>}
      </div>
    </section>
  </div>;
}

function FavoritesPage({
  products,
  favorites,
  onOpen,
  onFavorite,
  onDiscover,
}: {
  products: Product[];
  favorites: number[];
  onOpen: (id: number) => void;
  onFavorite: (id: number) => void;
  onDiscover: () => void;
}) {
  const savedProducts = products.filter((product) => favorites.includes(product.id));
  return (
    <main className="container page section">
      <div className="page-title"><div><h1>我的收藏</h1><p>留存你喜欢的原创手作</p></div></div>
      {savedProducts.length ? (
        <ProductGrid products={savedProducts} favorites={favorites} onOpen={onOpen} onFavorite={onFavorite} />
      ) : (
        <Empty title="还没有收藏作品" text="在作品详情页收藏喜欢的手作。" action="发现好物" onAction={onDiscover} />
      )}
    </main>
  );
}

function FollowingShops({
  shops,
  onDiscover,
  onUnfollow,
}: {
  shops: FollowedShop[];
  onDiscover: () => void;
  onUnfollow: (shop: FollowedShop) => void;
}) {
  return (
    <div className="container page section">
      <div className="page-title">
        <div>
          <h1>关注店铺</h1>
          <p>查看你已关注的独立创作者</p>
        </div>
      </div>
      {shops.length ? (
        <div className="followed-shop-list">
          {shops.map((shop) => (
            <article key={shop.id}>
              <Store size={22} />
              <b>{shop.name}</b>
              <button className="secondary" onClick={() => onUnfollow(shop)}>
                取消关注
              </button>
            </article>
          ))}
        </div>
      ) : (
        <Empty
          title="还没有关注店铺"
          text="在商品详情页关注喜欢的创作者。"
          action="发现好物"
          onAction={onDiscover}
        />
      )}
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
        购物袋 <small>{items.length} 件作品</small>
      </h1>
      {items.length ? (
        <div className="cart-layout">
          <div className="cart-list">
            {items.map(({ product, quantity, variants }) => (
              <div
                className="cart-item"
                key={`${product.id}-${JSON.stringify(variants || {})}`}
              >
                <img src={product.image} alt="" />
                <div>
                  <h3>{product.title}</h3>
                  <p>{product.shop}</p>
                  {Object.keys(variants || {}).length > 0 && (
                    <small className="selected-specs">
                      {Object.entries(variants || {})
                        .map(([name, value]) => `${name}: ${value}`)
                        .join(" · ")}
                    </small>
                  )}
                  <span>{money(product.price)}</span>
                  <div className="qty-controls">
                    <IconButton
                      icon={Minus}
                      label="减少"
                      onClick={() => onUpdate(product.id, quantity - 1, variants)}
                    />
                    <b>{quantity}</b>
                    <IconButton
                      icon={Plus}
                      label="增加"
                      onClick={() =>
                        onUpdate(
                          product.id,
                          Math.min(
                            quantity + 1,
                            product.skus?.find((sku) =>
                              Object.entries(variants || {}).every(
                                ([name, value]) => sku.optionValues[name] === value,
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
                  移除
                </button>
              </div>
            ))}
          </div>
          <aside className="summary">
            <h3>订单摘要</h3>
            <p>
              <span>商品小计</span>
              <b>{money(total)}</b>
            </p>
            <p>
              <span>配送费</span>
              <b>¥0.00</b>
            </p>
            <hr />
            <p className="total">
              <span>合计</span>
              <b>{money(total)}</b>
            </p>
            <button data-testid="cart-checkout" className="primary full" onClick={onCheckout}>
              去结算 <ChevronRight size={18} />
            </button>
            <small>提交订单后将确认支付并生成支付流水。</small>
          </aside>
        </div>
      ) : (
        <Empty
          title="购物袋还是空的"
          text="去挑一件让日常变得特别的小物吧。"
          action="发现好物"
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
  const [addressDraft, setAddressDraft] = useState({ recipient: "", phone: "", province: "", city: "", district: "", detail: "" });
  const [addressError, setAddressError] = useState("");
  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod>("alipay");
  useEffect(() => {
    if (!addresses.length) return;
    setSelectedAddressId((current) => current || addresses.find((address) => address.isDefault)?.id || addresses[0].id);
  }, [addresses]);
  useEffect(() => {
    if (!selectedAddressId || !data.cart.length) return;
    void onQuote(selectedAddressId).then(setQuote).catch((error: Error) => setAddressError(error.message));
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
        返回购物袋
      </button>
      <h1>确认订单</h1>
      <div className="checkout-layout">
        <div className="checkout-main">
          <section>
            <h3>
              <MapPin size={19} />
              收货地址
            </h3>
            <div className="address-list">
              {addresses.map((address) => (
                <label className={`address ${selectedAddressId === address.id ? "selected-address" : ""}`} key={address.id}>
                  <input type="radio" name="address" checked={selectedAddressId === address.id} onChange={() => setSelectedAddressId(address.id)} />
                  <b>{address.recipient} {address.phone}</b>
                  <p>{address.province}{address.city}{address.district}{address.detail}</p>
                  {address.isDefault && <span>默认地址</span>}
                </label>
              ))}
            </div>
            <div className="address-editor">
              <input data-testid="checkout-recipient" value={addressDraft.recipient} onChange={(event) => setAddressDraft((value) => ({ ...value, recipient: event.target.value }))} placeholder="收货人" />
              <input data-testid="checkout-phone" value={addressDraft.phone} onChange={(event) => setAddressDraft((value) => ({ ...value, phone: event.target.value }))} placeholder="手机号" />
              <input data-testid="checkout-province" value={addressDraft.province} onChange={(event) => setAddressDraft((value) => ({ ...value, province: event.target.value }))} placeholder="省" />
              <input data-testid="checkout-city" value={addressDraft.city} onChange={(event) => setAddressDraft((value) => ({ ...value, city: event.target.value }))} placeholder="市" />
              <input data-testid="checkout-district" value={addressDraft.district} onChange={(event) => setAddressDraft((value) => ({ ...value, district: event.target.value }))} placeholder="区/县" />
              <input data-testid="checkout-detail" value={addressDraft.detail} onChange={(event) => setAddressDraft((value) => ({ ...value, detail: event.target.value }))} placeholder="详细地址" />
              <button data-testid="checkout-add-address" className="secondary" type="button" onClick={async () => { try { const address = await onAddAddress({ ...addressDraft, isDefault: !addresses.length }); setSelectedAddressId(address.id); setAddressDraft({ recipient: "", phone: "", province: "", city: "", district: "", detail: "" }); } catch (error) { setAddressError(error instanceof Error ? error.message : "地址保存失败"); } }}>新增地址</button>
            </div>
            {addressError && <small className="checkout-error">{addressError}</small>}
          </section>
          <section>
            <h3>
              <CreditCard size={19} />
              支付方式
            </h3>
            <label className="payment-option">
              <input type="radio" checked={paymentMethod === "alipay"} name="pay" onChange={() => setPaymentMethod("alipay")} />
              <span className="pay-icon">¥</span>
              <b>支付宝</b>
              <em>推荐</em>
            </label>
            <label className="payment-option">
              <input type="radio" checked={paymentMethod === "card"} name="pay" onChange={() => setPaymentMethod("card")} />
              <span className="pay-icon card">▣</span>
              <b>银行卡</b>
            </label>
          </section>
          <section>
            <h3>
              <Package size={19} />
              订单商品
            </h3>
            {data.cart.map((i) => {
              const p = data.products.find((x) => x.id === i.productId)!;
              return (
                <div
                  className="checkout-item"
                  key={`${p.id}-${JSON.stringify(i.variants || {})}`}
                >
                  <img src={p.image} alt="" />
                  <span>
                    {p.title} × {i.quantity}
                    {Object.keys(i.variants || {}).length > 0 && (
                      <small className="selected-specs">
                        {Object.entries(i.variants || {})
                          .map(([name, value]) => `${name}: ${value}`)
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
          <h3>应付金额</h3>
          <p><span>商品小计</span><b>{money(quote?.itemAmount ?? total)}</b></p>
          <p><span>运费</span><b>{money(quote?.shippingAmount ?? 0)}</b></p>
          <p><span>优惠</span><b>-{money(quote?.discountAmount ?? 0)}</b></p>
          <p className="total">
            <span>合计</span>
            <b>{money(quote?.amount ?? total)}</b>
          </p>
          <button data-testid="checkout-submit" className="primary full" disabled={!selectedAddressId || !quote} onClick={() => onFinish(paymentMethod, selectedAddressId)}>
            提交订单并支付
          </button>
        </aside>
      </div>
    </div>
  );
}

function Orders({
  data,
  orders,
  afterSales,
  reviews,
  onShipping,
  onReceive,
  onCancel,
  onPay,
  onReview,
  onFollowup,
  onAfterSale,
  onReturnShipment,
}: {
  data: AppData;
  orders: Order[];
  afterSales: AfterSaleRequest[];
  reviews: ProductReview[];
  onShipping: (id: string) => void;
  onReceive: (id: string) => void;
  onCancel: (id: string) => void;
  onPay: (id: string, method: PaymentMethod) => Promise<boolean>;
  onReview: (id: string, draft: ReviewDraft) => Promise<boolean>;
  onFollowup: (reviewIds: Array<string | number>, content: string) => Promise<boolean>;
  onAfterSale: (id: string, draft: AfterSaleDraft) => Promise<boolean>;
  onReturnShipment: (id: string | number, draft: ReturnShipmentDraft) => Promise<boolean>;
}) {
  const [statusFilter, setStatusFilter] = useState("全部");
  const [afterSaleOrder, setAfterSaleOrder] = useState<Order | null>(null);
  const [reviewOrder, setReviewOrder] = useState<Order | null>(null);
  const [followupOrder, setFollowupOrder] = useState<Order | null>(null);
  const [returnShipmentRequest, setReturnShipmentRequest] = useState<AfterSaleRequest | null>(null);
  const visibleOrders = orders.filter((order) => statusFilter === "全部" || order.status === statusFilter);
  return (
    <div className="container page section">
      <div className="page-title">
        <div>
          <h1>订单中心</h1>
          <p>查看和管理你的购买订单</p>
        </div>
      </div>
      <div className="order-filters">
        {["全部", "待付款", "待发货", "待收货", "已完成", "已取消", "已退款"].map((status) => (
          <button className={statusFilter === status ? "selected" : ""} key={status} onClick={() => setStatusFilter(status)}>{status}</button>
        ))}
      </div>
      {visibleOrders.length ? (
        <div className="orders">
          {visibleOrders.map((order) => {
            const orderReviews = reviews.filter((review) => review.orderId === order.id);
            const orderAfterSale = afterSales.find((request) => request.orderId === order.id);
            return (
            <article className="order-card" data-testid="order-card" key={order.id}>
              <header>
                <span>订单号 {order.id}</span>
                <span>{order.createdAt}</span>
                <StatusPill status={order.status} />
              </header>
              {order.items.map((item) => {
                const p = data.products.find((x) => x.id === item.productId);
                return (
                  <div
                    className="order-product"
                    key={`${item.catalogId || item.productId}-${JSON.stringify(item.variants || {})}`}
                  >
                    {item.image || p?.image ? <img src={item.image || p?.image} alt="" /> : <span />}
                    <div>
                      <b>{item.title || p?.title || "作品"}</b>
                      <span>
                        数量 {item.quantity}
                        {Object.keys(item.variants || {}).length > 0 && (
                          <small className="selected-specs">
                            {" "}
                            ·{" "}
                            {Object.entries(item.variants || {})
                              .map(([name, value]) => `${name}: ${value}`)
                              .join(" · ")}
                          </small>
                        )}
                      </span>
                    </div>
                    <strong>{money((item.unitPrice || p?.price || 0) * item.quantity)}</strong>
                  </div>
                );
              })}
              <footer>
                <span>
                  合计 <b>{money(order.amount)}</b>
                  {(order.shippingAmount || order.discountAmount) ? <small className="order-amount-detail"> 商品 {money(order.itemAmount || 0)} · 运费 {money(order.shippingAmount || 0)} · 优惠 -{money(order.discountAmount || 0)}</small> : null}
                  {order.payment?.status === "succeeded" && <small data-testid="order-payment-confirmed" className="order-amount-detail">已支付 · {order.payment.method === "alipay" ? "支付宝" : "银行卡"}{order.payment.reference ? ` · ${order.payment.reference}` : ""}</small>}
                </span>
                <div>
                  {(order.status === "运输中" || order.status === "待收货") && (
                    <button
                      className="secondary"
                      onClick={() => onShipping(order.id)}
                    >
                      <Truck size={16} />
                      查看物流
                    </button>
                  )}
                  {order.status === "待收货" && (
                    <button
                      className="primary"
                      onClick={() => onReceive(order.id)}
                    >
                      确认收货
                    </button>
                  )}
                  {order.status === "待付款" && (
                    <button className="primary" onClick={() => void onPay(order.id, order.payment?.method || "alipay")}>立即支付</button>
                  )}
                  {order.status === "待付款" && (
                    <button className="secondary" onClick={() => onCancel(order.id)}>
                      取消订单
                    </button>
                  )}
                  {order.status === "已完成" && !order.reviewed && (
                    <button
                      className="secondary"
                      onClick={() => setReviewOrder(order)}
                    >
                      去评价
                    </button>
                  )}
                  {order.status === "已完成" && order.reviewed && (
                    <button
                      className="secondary"
                      disabled={!orderReviews.length}
                      onClick={() => setFollowupOrder(order)}
                    >
                      {orderReviews.some((review) => review.followup) ? "修改追评" : "追加评价"}
                    </button>
                  )}
                  {order.status !== "待付款" && order.status !== "已取消" && !afterSales.some((item) => item.orderId === order.id) && (
                    <button className="secondary" onClick={() => setAfterSaleOrder(order)}>
                      申请售后
                    </button>
                  )}
                </div>
              </footer>
              {orderAfterSale && (
                <AfterSaleProgress
                  request={orderAfterSale}
                  onReturnShipment={() => setReturnShipmentRequest(orderAfterSale)}
                />
              )}
            </article>
            );
          })}
        </div>
      ) : (
        <Empty
          title="还没有订单"
          text="购买心仪作品后，订单会出现在这里。"
          action="发现好物"
          onAction={() => location.reload()}
        />
      )}
      {afterSaleOrder && (
        <AfterSaleForm
          order={afterSaleOrder}
          onCancel={() => setAfterSaleOrder(null)}
          onSubmit={async (draft) => {
            if (await onAfterSale(afterSaleOrder.id, draft)) {
              setAfterSaleOrder(null);
            }
          }}
        />
      )}
      {reviewOrder && (
        <ReviewForm
          order={reviewOrder}
          onCancel={() => setReviewOrder(null)}
          onSubmit={async (draft) => {
            if (await onReview(reviewOrder.id, draft)) setReviewOrder(null);
          }}
        />
      )}
      {followupOrder && (
        <ReviewFollowupForm
          order={followupOrder}
          reviews={reviews.filter((review) => review.orderId === followupOrder.id)}
          onCancel={() => setFollowupOrder(null)}
          onSubmit={async (content) => {
            const orderReviewIds = reviews
              .filter((review) => review.orderId === followupOrder.id)
              .map((review) => review.id);
            if (orderReviewIds.length && await onFollowup(orderReviewIds, content)) {
              setFollowupOrder(null);
            }
          }}
        />
      )}
      {returnShipmentRequest && (
        <ReturnShipmentForm
          request={returnShipmentRequest}
          onCancel={() => setReturnShipmentRequest(null)}
          onSubmit={async (draft) => {
            if (await onReturnShipment(returnShipmentRequest.id, draft)) {
              setReturnShipmentRequest(null);
            }
          }}
        />
      )}
    </div>
  );
}

export function AfterSaleForm({
  order,
  onSubmit,
  onCancel,
}: {
  order: Order;
  onSubmit: (draft: AfterSaleDraft) => Promise<void>;
  onCancel: () => void;
}) {
  const [type, setType] = useState<AfterSaleDraft["type"]>("refund");
  const [amount, setAmount] = useState(String(order.amount));
  const [reason, setReason] = useState("");
  const [evidence, setEvidence] = useState<string[]>([]);
  const [error, setError] = useState("");
  const canSubmit = Number(amount) > 0 && Number(amount) <= order.amount && !!reason.trim();

  const addEvidence = async (files: FileList | null) => {
    if (!files?.length) return;
    const imageFiles = Array.from(files).filter((file) => file.type.startsWith("image/"));
    if (!imageFiles.length) {
      setError("请仅选择图片文件");
      return;
    }
    const available = Math.max(0, 6 - evidence.length);
    const selected = imageFiles.slice(0, available);
    if (!selected.length) {
      setError("最多上传 6 张凭证图片");
      return;
    }
    try {
      const images = await Promise.all(
        selected.map(
          (file) =>
            new Promise<string>((resolve, reject) => {
              const reader = new FileReader();
              reader.onload = () => resolve(String(reader.result));
              reader.onerror = () => reject(new Error("无法读取图片"));
              reader.readAsDataURL(file);
            }),
        ),
      );
      setEvidence((items) => [...items, ...images]);
      setError(imageFiles.length > selected.length ? "最多上传 6 张凭证图片" : "");
    } catch {
      setError("图片读取失败，请重新选择");
    }
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const requestedAmount = Number(amount);
    if (!Number.isFinite(requestedAmount) || requestedAmount <= 0) {
      setError("请输入有效的退款金额");
      return;
    }
    if (requestedAmount > order.amount) {
      setError("退款金额不能超过订单实付金额");
      return;
    }
    if (!reason.trim()) {
      setError("请填写申请原因");
      return;
    }
    await onSubmit({ type, amount: requestedAmount, reason: reason.trim(), evidence });
  };
  useEffect(() => {
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") onCancel();
    };
    document.addEventListener("keydown", closeOnEscape);
    return () => document.removeEventListener("keydown", closeOnEscape);
  }, [onCancel]);

  return (
    <div className="after-sale-form-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onCancel(); }}>
    <form data-testid="after-sale-form" className="after-sale-form after-sale-form-dialog" role="dialog" aria-modal="true" aria-labelledby="after-sale-form-title" onSubmit={submit}>
      <div className="after-sale-form-head">
        <div>
          <h2 id="after-sale-form-title">申请售后</h2>
          <p>订单号：{order.id}，实付金额 {money(order.amount)}</p>
        </div>
        <button className="icon-button" type="button" aria-label="关闭售后申请" title="关闭" onClick={onCancel}>
          <X size={18} />
        </button>
      </div>
      <div className="after-sale-type" role="radiogroup" aria-label="售后类型">
        <label className={type === "refund" ? "selected" : ""}>
          <input type="radio" name="after-sale-type" checked={type === "refund"} onChange={() => setType("refund")} />
          仅退款
        </label>
        <label className={type === "return_refund" ? "selected" : ""}>
          <input type="radio" name="after-sale-type" checked={type === "return_refund"} onChange={() => setType("return_refund")} />
          退货退款
        </label>
      </div>
      <label className="after-sale-field">
        <span>退款金额</span>
        <input data-testid="after-sale-amount" type="number" min="0.01" max={order.amount} step="0.01" value={amount} onChange={(event) => setAmount(event.target.value)} />
      </label>
      <label className="after-sale-field">
        <span>申请原因</span>
        <textarea data-testid="after-sale-reason" value={reason} maxLength={300} placeholder="请说明售后原因" onChange={(event) => setReason(event.target.value)} />
      </label>
      <div className="after-sale-field">
        <span>凭证图片 <small>最多 6 张</small></span>
        <div className="after-sale-evidence-editor">
          {evidence.map((image, index) => (
            <div className="after-sale-evidence-item" key={image}>
              <img src={image} alt={`凭证图片 ${index + 1}`} />
              <button type="button" aria-label={`移除凭证图片 ${index + 1}`} title="移除图片" onClick={() => setEvidence((items) => items.filter((_, itemIndex) => itemIndex !== index))}>
                <X size={14} />
              </button>
            </div>
          ))}
          {evidence.length < 6 && (
            <label className="after-sale-evidence-upload">
              <ImagePlus size={20} />
              <span>添加图片</span>
              <input type="file" accept="image/*" multiple onChange={(event) => {
                void addEvidence(event.target.files);
                event.target.value = "";
              }} />
            </label>
          )}
        </div>
      </div>
      {error && <p className="after-sale-error" role="alert">{error}</p>}
      <div className="after-sale-actions">
        <button className="secondary" type="button" onClick={onCancel}>取消</button>
        <button data-testid="after-sale-submit" className="primary" type="submit" disabled={!canSubmit}>提交申请</button>
      </div>
    </form>
    </div>
  );
}

function AfterSaleProgress({
  request,
  onReturnShipment,
}: {
  request: AfterSaleRequest;
  onReturnShipment: () => void;
}) {
  return (
    <section className="after-sale-progress">
      <div className="after-sale-progress-head">
        <div>
          <b>售后进度 · {request.type}</b>
          <span>退款金额 {money(request.amount || 0)}</span>
        </div>
        <StatusPill status={request.status as OrderStatus} />
      </div>
      {request.sellerResponse && <p className="after-sale-response">卖家处理：{request.sellerResponse}</p>}
      {request.returnShipment && <p className="after-sale-shipment">退回物流：{request.returnShipment.carrier} · {request.returnShipment.trackingNo}</p>}
      {request.timeline?.length ? (
        <ol className="after-sale-timeline">
          {request.timeline.map((event, index) => (
            <li key={`${event.time}-${index}`}>
              <i />
              <div><b>{event.label}</b><span>{event.detail}</span><time>{event.time}</time></div>
            </li>
          ))}
        </ol>
      ) : null}
      {request.type === "退货退款" && request.status === "待退货" && (
        <div className="after-sale-return-action">
          <p>退货地址：{request.returnAddress || "请联系卖家确认退货地址"}</p>
          <button className="primary" onClick={onReturnShipment}>填写退回物流</button>
        </div>
      )}
    </section>
  );
}

function ReturnShipmentForm({
  request,
  onSubmit,
  onCancel,
}: {
  request: AfterSaleRequest;
  onSubmit: (draft: ReturnShipmentDraft) => Promise<void>;
  onCancel: () => void;
}) {
  const [carrier, setCarrier] = useState("");
  const [trackingNo, setTrackingNo] = useState("");
  return (
    <form
      className="after-sale-form return-shipment-form"
      onSubmit={async (event) => {
        event.preventDefault();
        if (!carrier.trim() || !trackingNo.trim()) return;
        await onSubmit({ carrier: carrier.trim(), trackingNo: trackingNo.trim() });
      }}
    >
      <div className="after-sale-form-head">
        <div><h2>填写退回物流</h2><p>退款金额 {money(request.amount || 0)}</p></div>
        <button className="icon-button" type="button" aria-label="关闭退货物流表单" title="关闭" onClick={onCancel}><X size={18} /></button>
      </div>
      <p className="return-address">退货地址：{request.returnAddress || "请联系卖家确认退货地址"}</p>
      <label className="after-sale-field"><span>快递公司</span><input value={carrier} maxLength={40} placeholder="例如：顺丰速运" onChange={(event) => setCarrier(event.target.value)} /></label>
      <label className="after-sale-field"><span>运单号</span><input value={trackingNo} maxLength={60} placeholder="请输入退回运单号" onChange={(event) => setTrackingNo(event.target.value)} /></label>
      <div className="after-sale-actions">
        <button className="secondary" type="button" onClick={onCancel}>取消</button>
        <button className="primary" type="submit" disabled={!carrier.trim() || !trackingNo.trim()}>提交物流</button>
      </div>
    </form>
  );
}

function AfterSaleDecisionForm({
  request,
  action,
  onSubmit,
  onCancel,
}: {
  request: AfterSaleRequest;
  action: "approve" | "reject" | "receive";
  onSubmit: (response: string) => Promise<void>;
  onCancel: () => void;
}) {
  const defaultResponse = action === "reject"
    ? ""
    : action === "receive"
      ? "已确认收到退回作品，退款已完成"
      : request.type === "退货退款"
        ? "同意退货退款，请按退货地址寄回作品"
        : "已同意退款，退款已完成";
  const [response, setResponse] = useState(defaultResponse);
  const title = action === "reject" ? "拒绝售后申请" : action === "receive" ? "确认收到退货" : request.type === "退货退款" ? "同意退货退款" : "同意退款";
  return (
    <form
      className="studio-panel after-sale-decision-form"
      onSubmit={async (event) => {
        event.preventDefault();
        if (!response.trim()) return;
        await onSubmit(response.trim());
      }}
    >
      <div className="panel-head"><h3>{title}</h3><button className="icon-button" type="button" aria-label="关闭售后处理表单" title="关闭" onClick={onCancel}><X size={18} /></button></div>
      <p>订单 {request.orderId} · 退款金额 {money(request.amount || 0)}</p>
      {action === "approve" && request.type === "退货退款" && <p className="return-address">买家会看到退货地址：{request.returnAddress || "请先在店铺设置填写地址"}</p>}
      {action === "receive" && request.returnShipment && <p className="return-address">退回物流：{request.returnShipment.carrier} · {request.returnShipment.trackingNo}</p>}
      <label>
        {action === "reject" ? "拒绝原因" : "处理说明"}
        <textarea value={response} maxLength={300} placeholder={action === "reject" ? "请说明拒绝原因" : "填写给买家的处理说明"} onChange={(event) => setResponse(event.target.value)} />
      </label>
      <div className="after-sale-actions">
        <button className="secondary" type="button" onClick={onCancel}>取消</button>
        <button className="primary" type="submit" disabled={!response.trim()}>{action === "reject" ? "确认拒绝" : action === "receive" ? "确认收货并退款" : "确认处理"}</button>
      </div>
    </form>
  );
}

export function ReviewForm({
  order,
  onSubmit,
  onCancel,
}: {
  order: Order;
  onSubmit: (draft: ReviewDraft) => Promise<void>;
  onCancel: () => void;
}) {
  const [rating, setRating] = useState(5);
  const [content, setContent] = useState("");
  const [images, setImages] = useState<string[]>([]);
  const [error, setError] = useState("");

  const addImages = async (files: FileList | null) => {
    if (!files?.length) return;
    const selectedFiles = Array.from(files).filter((file) => file.type.startsWith("image/"));
    if (!selectedFiles.length) {
      setError("请仅选择图片文件");
      return;
    }
    const available = Math.max(0, 6 - images.length);
    const filesToRead = selectedFiles.slice(0, available);
    if (!filesToRead.length) {
      setError("最多上传 6 张评价图片");
      return;
    }
    try {
      const nextImages = await Promise.all(
        filesToRead.map(
          (file) =>
            new Promise<string>((resolve, reject) => {
              const reader = new FileReader();
              reader.onload = () => resolve(String(reader.result));
              reader.onerror = () => reject(new Error("无法读取图片"));
              reader.readAsDataURL(file);
            }),
        ),
      );
      setImages((value) => [...value, ...nextImages]);
      setError(selectedFiles.length > filesToRead.length ? "最多上传 6 张评价图片" : "");
    } catch {
      setError("图片读取失败，请重新选择");
    }
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!content.trim()) {
      setError("请填写评价内容");
      return;
    }
    await onSubmit({ rating, content: content.trim(), images });
  };

  return (
    <form data-testid="review-form" className="review-form" onSubmit={submit}>
      <div className="review-form-head">
        <div>
          <h2>评价作品</h2>
          <p>订单号：{order.id}</p>
        </div>
        <button className="icon-button" type="button" aria-label="关闭评价表单" title="关闭" onClick={onCancel}>
          <X size={18} />
        </button>
      </div>
      <div className="review-field">
        <span>综合评分</span>
        <div className="review-rating" role="radiogroup" aria-label="综合评分">
          {[1, 2, 3, 4, 5].map((value) => (
            <button
              className={value <= rating ? "selected" : ""}
              key={value}
              type="button"
              aria-label={`${value} 星`}
              aria-pressed={value === rating}
              onClick={() => setRating(value)}
            >
              <Star size={26} fill="currentColor" />
            </button>
          ))}
          <b>{rating} 星</b>
        </div>
      </div>
      <label className="review-field">
        <span>评价内容</span>
        <textarea data-testid="review-content" value={content} maxLength={500} placeholder="分享作品使用感受与制作细节" onChange={(event) => setContent(event.target.value)} />
      </label>
      <div className="review-field">
        <span>评价图片 <small>最多 6 张</small></span>
        <div className="review-image-editor">
          {images.map((image, index) => (
            <div className="review-image-item" key={image}>
              <img src={image} alt={`评价图片 ${index + 1}`} />
              <button type="button" aria-label={`移除评价图片 ${index + 1}`} title="移除图片" onClick={() => setImages((items) => items.filter((_, itemIndex) => itemIndex !== index))}>
                <X size={14} />
              </button>
            </div>
          ))}
          {images.length < 6 && (
            <label className="review-image-upload">
              <ImagePlus size={20} />
              <span>添加图片</span>
              <input type="file" accept="image/*" multiple onChange={(event) => {
                void addImages(event.target.files);
                event.target.value = "";
              }} />
            </label>
          )}
        </div>
      </div>
      {error && <p className="review-form-error" role="alert">{error}</p>}
      <div className="review-form-actions">
        <button className="secondary" type="button" onClick={onCancel}>取消</button>
        <button data-testid="review-submit" className="primary" type="submit" disabled={!content.trim()}>提交评价</button>
      </div>
    </form>
  );
}

function ReviewFollowupForm({
  order,
  reviews,
  onSubmit,
  onCancel,
}: {
  order: Order;
  reviews: ProductReview[];
  onSubmit: (content: string) => Promise<void>;
  onCancel: () => void;
}) {
  const [content, setContent] = useState(reviews.find((review) => review.followup)?.followup || "");
  return (
    <form
      className="review-form review-followup-form"
      onSubmit={async (event) => {
        event.preventDefault();
        if (!content.trim()) return;
        await onSubmit(content.trim());
      }}
    >
      <div className="review-form-head">
        <div><h2>追加评价</h2><p>订单号：{order.id}</p></div>
        <button className="icon-button" type="button" aria-label="关闭追评表单" title="关闭" onClick={onCancel}><X size={18} /></button>
      </div>
      <label className="review-field">
        <span>追评内容</span>
        <textarea value={content} maxLength={500} placeholder="补充使用后的感受" onChange={(event) => setContent(event.target.value)} />
      </label>
      <div className="review-form-actions">
        <button className="secondary" type="button" onClick={onCancel}>取消</button>
        <button className="primary" type="submit" disabled={!content.trim()}>提交追评</button>
      </div>
    </form>
  );
}

export function ShipmentForm({ order, onSubmit, onCancel }: { order: Order; onSubmit: (draft: ShipmentDraft) => Promise<void>; onCancel: () => void }) {
  const [carrier, setCarrier] = useState("");
  const [trackingNo, setTrackingNo] = useState("");
  useEffect(() => {
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") onCancel();
    };
    document.addEventListener("keydown", closeOnEscape);
    return () => document.removeEventListener("keydown", closeOnEscape);
  }, [onCancel]);
  return <div className="shipment-form-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onCancel(); }}>
    <form data-testid="shipment-form" className="studio-panel shipment-form shipment-form-dialog" role="dialog" aria-modal="true" aria-labelledby="shipment-form-title" onSubmit={async (event) => { event.preventDefault(); if (carrier.trim() && trackingNo.trim()) await onSubmit({ carrier: carrier.trim(), trackingNo: trackingNo.trim() }); }}>
      <div className="panel-head"><h3 id="shipment-form-title">填写发货信息</h3><button className="icon-button" type="button" aria-label="关闭发货表单" title="关闭" onClick={onCancel}><X size={18} /></button></div>
      <p>订单 {order.id} · {money(order.amount)}</p>
      <label>快递公司<input data-testid="shipment-carrier" value={carrier} maxLength={40} placeholder="例如：顺丰速运" onChange={(event) => setCarrier(event.target.value)} /></label>
      <label>运单号<input data-testid="shipment-tracking" value={trackingNo} maxLength={60} placeholder="请输入快递单号" onChange={(event) => setTrackingNo(event.target.value)} /></label>
      <div className="after-sale-actions"><button className="secondary" type="button" onClick={onCancel}>取消</button><button data-testid="shipment-submit" className="primary" type="submit" disabled={!carrier.trim() || !trackingNo.trim()}>确认发货</button></div>
    </form>
  </div>;
}

function ShipmentEventForm({ order, onSubmit, onCancel }: { order: Order; onSubmit: (label: string, detail: string) => Promise<void>; onCancel: () => void }) {
  const [label, setLabel] = useState("");
  const [detail, setDetail] = useState("");
  return <form className="studio-panel shipment-form" onSubmit={async (event) => { event.preventDefault(); if (label.trim()) await onSubmit(label.trim(), detail.trim()); }}>
    <div className="panel-head"><h3>更新物流节点</h3><button className="icon-button" type="button" aria-label="关闭物流表单" title="关闭" onClick={onCancel}><X size={18} /></button></div>
    <p>{order.shipment?.carrier} · {order.shipment?.trackingNo}</p>
    <label>物流状态<input value={label} maxLength={60} placeholder="例如：包裹已到达杭州转运中心" onChange={(event) => setLabel(event.target.value)} /></label>
    <label>补充说明<input value={detail} maxLength={120} placeholder="可选" onChange={(event) => setDetail(event.target.value)} /></label>
    <div className="after-sale-actions"><button className="secondary" type="button" onClick={onCancel}>取消</button><button className="primary" type="submit" disabled={!label.trim()}>更新物流</button></div>
  </form>;
}

function ShippingModal({ order, onClose }: { order?: Order; onClose: () => void }) {
  useEffect(() => {
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", closeOnEscape);
    return () => document.removeEventListener("keydown", closeOnEscape);
  }, [onClose]);

  return (
    <div className="shipping-modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <section className="shipping-modal" role="dialog" aria-modal="true" aria-labelledby="shipping-modal-title">
        <header>
          <h2 id="shipping-modal-title">物流详情</h2>
          <IconButton icon={X} label="关闭物流详情" onClick={onClose} />
        </header>
        {!order?.shipment ? (
          <div className="shipping-modal-empty"><Truck size={28} /><b>暂无物流信息</b><p>卖家发货后会在这里显示快递与物流节点。</p></div>
        ) : (
          <section className="shipping-card">
            <div className="shipping-head">
              <span className="truck-circle"><Truck size={25} /></span>
              <div>
                <b>{order.status === "已完成" ? "已签收" : "运输中"}</b>
                <p>{order.shipment.carrier} · {order.shipment.trackingNo}</p>
              </div>
            </div>
            {(() => {
              const tracking = shipmentTrackingLink(order.shipment.carrier, order.shipment.trackingNo);
              return <div className="shipping-tracking-actions">
                <a className="primary shipping-tracking-link" href={tracking.url} target="_blank" rel="noreferrer">
                  {tracking.official ? `在 ${order.shipment.carrier} 官网查询` : "使用国际物流查询"}
                  <ChevronRight size={16} />
                </a>
                {tracking.requiresPhoneLast4 && order.shipment.trackingPhoneLast4 && <span className="shipping-phone-hint">查询物流信息请输入该四位号码：{order.shipment.trackingPhoneLast4}</span>}
              </div>;
            })()}
            <div className="timeline">
              {order.shipment.events.map((event, index) => (
                <div className="timeline-item" key={event.time + index}>
                  <i />
                  <div><b>{event.label}</b><p>{event.detail}</p><time>{event.time}</time></div>
                </div>
              ))}
            </div>
          </section>
        )}
      </section>
    </div>
  );
}

function ShopPage({
  shop,
  products,
  onOpen,
  onStudio,
}: {
  shop: Shop;
  products: Product[];
  onOpen: (id: number) => void;
  onStudio: () => void;
}) {
  const featuredProducts = products.filter((product) =>
    shop.featuredProductIds?.includes(product.id),
  );
  return (
    <div className="shop-page">
      <section
        className={`shop-hero ${shop.status === "paused" ? "shop-hero-paused" : ""}`}
        style={{
          backgroundImage: `url(${shop.banner})`,
        }}
      >
        <div className="container">
          <img src={shop.avatar} alt="" />
          <div>
            <p>独立创作者店铺</p>
            <h1>{shop.name}</h1>
            <span>
              {shop.status === "paused" ? "暂休中" : "营业中"} · {shop.location} · 自 {shop.since} 年
            </span>
          </div>
          {shop.status === "paused" && (
            <div className="shop-rest-sign" aria-label="店铺暂休中">
              <div className="shop-rest-chain shop-rest-chain-left" aria-hidden="true"><i /><i /><i /><i /></div>
              <div className="shop-rest-chain shop-rest-chain-right" aria-hidden="true"><i /><i /><i /><i /></div>
              <div className="shop-rest-sign-board"><b>暂休中</b><small>SHOP RESTING</small></div>
            </div>
          )}
        </div>
      </section>
      {shop.status === "paused" && <section className="shop-paused-notice"><div className="container"><b>店铺暂休中</b><span>店主暂不接受新的订单，已产生的订单仍会正常处理。有事请留言~</span></div></section>}
      <section className="container section">
        <div className="shop-intro">
          <div>
            <h2>关于 {shop.name}</h2>
            <p>{shop.description}</p>
          </div>
          <div>
            <b>{shop.followers.toLocaleString()}</b>
            <span>关注者</span>
          </div>
          <div>
            <b>
              4.9 <Star size={16} fill="currentColor" />
            </b>
            <span>店铺评分</span>
          </div>
        </div>
        {(shop.shippingOrigin || shop.coupons?.length) && (
          <div className="shop-operations">
            {shop.shippingOrigin && (
              <span>
                发货地：{shop.shippingOrigin}
                {shop.shippingTemplate && ` · ${shop.shippingTemplate.name}`}
              </span>
            )}
            {!!shop.coupons?.length && (
              <div>
                {shop.coupons.map((coupon) => (
                  <span key={coupon.id}>
                    满 {money(coupon.threshold)} 减 {money(coupon.discount)}
                  </span>
                ))}
              </div>
            )}
          </div>
        )}
        {!!featuredProducts.length && (
          <>
            <div className="section-heading featured-heading">
              <h2>店铺推荐</h2>
              <span>精选作品</span>
            </div>
            <ProductGrid
              products={featuredProducts}
              favorites={[]}
              onOpen={onOpen}
              onFavorite={() => {}}
            />
          </>
        )}
        <div className="section-heading">
          <h2>店铺作品</h2>
          <span>{products.length || 0} 件上架中</span>
        </div>
        {products.length ? (
          <ProductGrid
            products={products}
            favorites={[]}
            onOpen={onOpen}
            onFavorite={() => {}}
          />
        ) : (
          <Empty
            title="还未上架作品"
            text="在店主工作台发布你的第一件手作。"
            action="去发布"
            onAction={onStudio}
          />
        )}
      </section>
    </div>
  );
}

function AdminFinanceOperations() {
  type Withdrawal = { id: string; shop: string; applicant: string; amount: number; recipientType: string; recipient: string; status: string; note?: string; createdAt: string };
  const [finance, setFinance] = useState<{ feeRateBps: number; summary: { available: number; pending: number; withdrawing: number; withdrawn: number; platformFees: number }; withdrawals: Withdrawal[] } | null>(null);
  const [feeRate, setFeeRate] = useState("");
  const [notice, setNotice] = useState("");
  const load = async () => { const response = await fetch(`${API_BASE}/api/admin/finance`, { credentials: "include" }); const payload = await response.json().catch(() => ({})) as typeof finance & { error?: string }; if (!response.ok || !payload) return setNotice(payload?.error || "资金数据加载失败"); setFinance(payload); setFeeRate(String(payload.feeRateBps / 100)); };
  useEffect(() => { void load(); }, []);
  const stepUp = async (action: (ticket: string) => Promise<void>) => { const requested = await fetch(`${API_BASE}/api/auth/request-admin-step-up`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: "{}" }); const issue = await requested.json().catch(() => ({})) as { developmentCode?: string; error?: string }; if (!requested.ok) return setNotice(issue.error || "无法请求二次验证"); const code = window.prompt(`请输入二次验证码${issue.developmentCode ? `（开发验证码：${issue.developmentCode}）` : ""}`); if (!code) return; const confirmed = await fetch(`${API_BASE}/api/auth/confirm-admin-step-up`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ code }) }); const verified = await confirmed.json().catch(() => ({})) as { ticket?: string; error?: string }; if (!confirmed.ok || !verified.ticket) return setNotice(verified.error || "二次验证失败"); await action(verified.ticket); };
  const updateWithdrawal = (id: string, decision: "approved" | "rejected" | "paid") => void stepUp(async (ticket) => { const note = decision === "rejected" ? window.prompt("驳回原因") : ""; if (decision === "rejected" && !note) return; const response = await fetch(`${API_BASE}/api/admin/withdrawals/${encodeURIComponent(id)}`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json", "X-Admin-Step-Up": ticket }, body: JSON.stringify({ decision, note }) }); const payload = await response.json().catch(() => ({})) as { error?: string }; if (!response.ok) return setNotice(payload.error || "提现处理失败"); setNotice("提现状态已更新"); void load(); });
  return <section className="studio-panel admin-operations finance-admin"><div className="panel-head"><h2>结算与商家资金</h2><button className="secondary" onClick={() => void load()}>刷新</button></div>{notice && <p className="auth-error">{notice}</p>}
    <div className="metric-grid"><Metric label="商家可提现" value={money(finance?.summary.available || 0)} trend="未发起提现" /><Metric label="待结算" value={money(finance?.summary.pending || 0)} trend="等待收货" /><Metric label="提现中" value={money(finance?.summary.withdrawing || 0)} trend="待审核或打款" /><Metric label="平台服务费" value={money(finance?.summary.platformFees || 0)} trend="未冲回订单" /></div>
    <div className="admin-operation-grid"><form onSubmit={(event) => { event.preventDefault(); void stepUp(async (ticket) => { const response = await fetch(`${API_BASE}/api/admin/finance/settings`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json", "X-Admin-Step-Up": ticket }, body: JSON.stringify({ serviceFeeBps: Math.round(Number(feeRate) * 100) }) }); const payload = await response.json().catch(() => ({})) as { error?: string }; if (!response.ok) return setNotice(payload.error || "费率保存失败"); setNotice("新订单服务费率已保存"); void load(); }); }}><h3>平台服务费率</h3><input required type="number" min="0" max="30" step="0.01" value={feeRate} onChange={(event) => setFeeRate(event.target.value)} /><small>仅影响之后支付的订单，历史结算单费率保持不变。</small><button className="primary">保存费率</button></form><div><h3>提现审核队列</h3><div className="finance-list">{finance?.withdrawals.map((item) => <div key={item.id}><span><b>{item.shop} · {money(item.amount)}</b><small>{item.applicant} · {item.recipientType === "bank" ? "银行卡" : "电子钱包"} · {item.recipient}</small></span><span><b>{item.status}</b>{item.status === "pending" && <button className="secondary" onClick={() => updateWithdrawal(item.id, "approved")}>通过</button>}{item.status === "pending" && <button className="danger" onClick={() => updateWithdrawal(item.id, "rejected")}>驳回</button>}{item.status === "approved" && <button className="primary" onClick={() => updateWithdrawal(item.id, "paid")}>标记已打款</button>}</span></div>) || <p>暂无提现申请。</p>}</div></div></div>
  </section>;
}

function FinanceCenter({ toast }: { toast: (message: string) => void }) {
  type Finance = {
    feeRateBps: number;
    wallet: { available: number; pending: number; withdrawing: number; withdrawn: number };
    shops: { id: string; name: string; available: number; pending: number; withdrawing: number; withdrawn: number }[];
    settlements: { id: string; orderNo: string; gross: number; fee: number; net: number; status: string; createdAt: string; availableAt?: string }[];
    ledger: { id: string; type: string; availableDelta: number; pendingDelta: number; withdrawingDelta: number; withdrawnDelta: number; note: string; createdAt: string }[];
    withdrawals: { id: string; shopId: string; shop: string; amount: number; recipientType: string; recipient: string; status: string; note?: string; createdAt: string }[];
  };
  const [finance, setFinance] = useState<Finance | null>(null);
  const [payoutAccount, setPayoutAccount] = useState<{ provider: string; status: string; accountMask?: string | null; boundAt?: string | null; mode?: string } | null>(null);
  const [amount, setAmount] = useState("");
  const [recipientType, setRecipientType] = useState<"bank" | "wallet">("bank");
  const [recipient, setRecipient] = useState("");
  const [selectedShopId, setSelectedShopId] = useState("");
  const load = async () => {
    const response = await fetch(`${API_BASE}/api/seller/finance`, { credentials: "include" });
    const payload = await response.json().catch(() => ({})) as Finance & { error?: string };
    if (!response.ok) return toast(payload.error || "资金数据加载失败");
    setFinance(payload);
  };
  useEffect(() => { void load(); }, []);
  const loadPayoutAccount = async () => {
    const response = await fetch(`${API_BASE}/api/seller/payout-account`, { credentials: "include" });
    if (response.ok) setPayoutAccount(((await response.json()) as { payoutAccount: typeof payoutAccount }).payoutAccount);
  };
  useEffect(() => { void loadPayoutAccount(); }, []);
  useEffect(() => { if (!selectedShopId && finance?.shops[0]) setSelectedShopId(finance.shops[0].id); }, [finance, selectedShopId]);
  const bindPayoutAccount = async () => {
    const accountName = window.prompt("请输入连连实名姓名");
    if (!accountName) return;
    const bankCard = window.prompt("本地 mock 模式请输入银行卡号（生产环境将跳转连连安全页面）");
    if (!bankCard) return;
    const response = await fetch(`${API_BASE}/api/seller/payout-account/onboarding`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ accountName, bankCard }) });
    const payload = await response.json().catch(() => ({})) as { error?: string; payoutAccount?: typeof payoutAccount };
    if (!response.ok) return toast(payload.error || "连连账户绑定失败");
    if (payload.payoutAccount) setPayoutAccount(payload.payoutAccount);
    toast("连连收款账户已绑定");
  };
  const requestWithdrawal = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const shopId = selectedShopId || finance?.shops[0]?.id;
    if (!shopId) return toast("未找到可提现店铺");
    const response = await fetch(`${API_BASE}/api/seller/withdrawals`, {
      method: "POST", credentials: "include", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ shopId, amount: Number(amount), recipientType, recipient }),
    });
    const payload = await response.json().catch(() => ({})) as { error?: string };
    if (!response.ok) return toast(payload.error || "提现申请失败");
    setAmount(""); setRecipient(""); toast("提现申请已提交，等待平台审核"); void load();
  };
  const settlementStatus: Record<string, string> = { pending: "待结算", available: "可提现", reversed: "已冲回" };
  const withdrawalStatus: Record<string, string> = { pending: "待审核", approved: "待打款", rejected: "已驳回", paid: "已打款" };
  return <>
    <div className="studio-title"><div><h1>结算与资金</h1><p>订单付款后进入待结算，买家确认收货后可申请提现。</p></div></div>
    <div className="metric-grid finance-metrics">
      <Metric label="可提现" value={money(finance?.wallet.available || 0)} trend="可提交提现申请" />
      <Metric label="待结算" value={money(finance?.wallet.pending || 0)} trend="等待买家确认收货" />
      <Metric label="提现中" value={money(finance?.wallet.withdrawing || 0)} trend="平台审核或打款中" />
      <Metric label="累计已提现" value={money(finance?.wallet.withdrawn || 0)} trend="已完成打款" />
    </div>
    <section className="studio-panel payout-binding-panel"><div className="panel-head"><div><h3>连连收款账户</h3><small>卖家收款需先完成连连实名和银行卡绑定。</small></div><span className={`seller-payout-status ${payoutAccount?.status || "unbound"}`}>{payoutAccount?.status === "bound" ? `已绑定 ${payoutAccount.accountMask || ""}` : "未绑定"}</span></div><button className="secondary" onClick={() => void bindPayoutAccount()}>{payoutAccount?.status === "bound" ? "重新绑定" : "绑定连连账户"}</button>{payoutAccount?.mode !== "mock" && <small className="auth-hint">当前服务未配置连连商户参数，绑定按钮将在配置完成后启用。</small>}</section>
    <div className="finance-layout">
      <section className="studio-panel settings-form"><div className="panel-head"><h3>申请提现</h3><small>平台服务费率 {(finance?.feeRateBps || 0) / 100}%</small></div>
        <form onSubmit={requestWithdrawal} className="finance-form">
          {finance && finance.shops.length > 1 && <label>结算店铺<select value={selectedShopId} onChange={(event) => setSelectedShopId(event.target.value)}>{finance.shops.map((shop) => <option value={shop.id} key={shop.id}>{shop.name} · 可提现 {money(shop.available)}</option>)}</select></label>}
          <label>提现金额<input required type="number" min="0.01" step="0.01" max={(finance?.shops.find((shop) => shop.id === selectedShopId)?.available ?? finance?.wallet.available) || 0} value={amount} onChange={(event) => setAmount(event.target.value)} placeholder="0.00" /></label>
          <label>收款方式<select value={recipientType} onChange={(event) => setRecipientType(event.target.value as "bank" | "wallet")}><option value="bank">银行卡</option><option value="wallet">电子钱包</option></select></label>
          <label>收款账户<input required maxLength={500} value={recipient} onChange={(event) => setRecipient(event.target.value)} placeholder={recipientType === "bank" ? "开户名、开户行及账号" : "钱包账号"} /></label>
          <button className="primary" disabled={!finance?.wallet.available}>提交提现申请</button>
        </form>
      </section>
      <section className="studio-panel"><div className="panel-head"><h3>提现记录</h3><button className="text-link" onClick={() => void load()}>刷新</button></div>
        <div className="finance-list">{finance?.withdrawals.slice(0, 8).map((item) => <div key={item.id}><span><b>{money(item.amount)}</b><small>{item.recipientType === "bank" ? "银行卡" : "电子钱包"} · {item.recipient}</small></span><span><b>{withdrawalStatus[item.status] || item.status}</b><small>{item.createdAt}</small></span></div>) || <p>暂无提现记录。</p>}</div>
      </section>
    </div>
    <section className="studio-panel finance-table"><div className="panel-head"><h3>订单结算单</h3><small>服务费按订单支付时的费率固定</small></div>
      <div className="finance-list">{finance?.settlements.map((item) => <div key={item.id}><span><b>{item.orderNo}</b><small>{item.createdAt}</small></span><span><small>交易额 {money(item.gross)} · 服务费 {money(item.fee)}</small><b>净额 {money(item.net)} · {settlementStatus[item.status] || item.status}</b></span></div>) || <p>暂无已支付订单。</p>}</div>
    </section>
    <section className="studio-panel finance-table"><div className="panel-head"><h3>资金流水</h3></div>
      <div className="finance-list">{finance?.ledger.map((item) => <div key={item.id}><span><b>{item.note}</b><small>{item.createdAt}</small></span><b>{[item.availableDelta, item.pendingDelta, item.withdrawingDelta, item.withdrawnDelta].filter(Boolean).map((value) => `${value > 0 ? "+" : ""}${money(value)}`).join(" · ") || "0.00"}</b></div>) || <p>暂无资金流水。</p>}</div>
    </section>
  </>;
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
  onAddShipmentEvent: (id: string, label: string, detail: string) => Promise<boolean>;
  onResolveAfterSale: (id: string | number, action: "approve" | "reject", response: string) => Promise<boolean>;
  onReceiveReturn: (id: string | number, response: string) => Promise<boolean>;
  onReplyReview: (id: string | number, reply: string) => Promise<boolean>;
  toast: (s: string) => void;
}) {
  const [tab, setTab] = useState<
    "overview" | "products" | "inventory" | "orders" | "messages" | "reviews" | "shipping" | "service" | "promotions" | "finance" | "settings"
  >("overview");
  const [showForm, setShowForm] = useState(false);
  const [shipmentOrder, setShipmentOrder] = useState<Order | null>(null);
  const [shipmentEventOrder, setShipmentEventOrder] = useState<Order | null>(null);
  const [afterSaleDecision, setAfterSaleDecision] = useState<{ request: AfterSaleRequest; action: "approve" | "reject" | "receive" } | null>(null);
  const [replyingReviewId, setReplyingReviewId] = useState<string | number | null>(null);
  const [reviewReply, setReviewReply] = useState("");
  const sellerProducts = data.products.filter((p) => p.shopId === 99);
  const [productListMode, setProductListMode] = useState<"listed" | "trash">(
    "listed",
  );
  const listedSellerProducts = sellerProducts.filter((p) => p.listed !== false);
  const recycledSellerProducts = sellerProducts.filter((p) => p.listed === false);
  const displayedSellerProducts =
    productListMode === "listed" ? listedSellerProducts : recycledSellerProducts;
  const [editingProductId, setEditingProductId] = useState<number | null>(null);
  const [editingProductCatalogId, setEditingProductCatalogId] = useState<string | null>(null);
  const [editingDraftId, setEditingDraftId] = useState<number | null>(null);
  const [editingDraftCatalogId, setEditingDraftCatalogId] = useState<string | null>(null);
  const [selectedProductIds, setSelectedProductIds] = useState<number[]>([]);
  const [bulkPrice, setBulkPrice] = useState("");
  const [bulkStock, setBulkStock] = useState("");
  const [inventoryProductId, setInventoryProductId] = useState<number | null>(null);
  const [inventorySkuId, setInventorySkuId] = useState("");
  const [inventorySearch, setInventorySearch] = useState("");
  const [inventorySearchOpen, setInventorySearchOpen] = useState(false);
  const [inventoryAdjustmentType, setInventoryAdjustmentType] = useState<"set" | "increase" | "decrease">("increase");
  const [inventoryQuantity, setInventoryQuantity] = useState("");
  const [inventoryReason, setInventoryReason] = useState("");
  const [inventorySelectedSkuIds, setInventorySelectedSkuIds] = useState<string[]>([]);
  const [inventoryRowValues, setInventoryRowValues] = useState<Record<string, string>>({});
  const [inventoryListReason, setInventoryListReason] = useState("");
  const [inventoryAdjustments, setInventoryAdjustments] = useState<InventoryAdjustment[]>([]);
  const [form, setForm] = useState({
    title: "",
    price: "",
    category: "陶艺" as Category,
    stock: "10",
    lowStockThreshold: "3",
    description: "",
    images: [] as string[],
    video: "",
    seoTags: [] as string[],
  });
  const [seoTagInput, setSeoTagInput] = useState("");
  const [draggedImageIndex, setDraggedImageIndex] = useState<number | null>(
    null,
  );
  const [dragOverImageIndex, setDragOverImageIndex] = useState<number | null>(
    null,
  );
  const [variantDrafts, setVariantDrafts] = useState<
    {
      id: number;
      name: string;
      values: { id: number; value: string; image?: string }[];
    }[]
  >([]);
  const [skuStocks, setSkuStocks] = useState<Record<string, string>>({});
  const [skuPrices, setSkuPrices] = useState<Record<string, string>>({});
  const [skuCodes, setSkuCodes] = useState<Record<string, string>>({});
  const [skuStatuses, setSkuStatuses] = useState<Record<string, "active" | "disabled">>({});
  const [couponDraft, setCouponDraft] = useState({ threshold: "", discount: "" });
  const [visitorCount, setVisitorCount] = useState(0);
  const [analyticsDays, setAnalyticsDays] = useState<7 | 30>(30);
  const [analytics, setAnalytics] = useState<{ revenue: number; orders: number; visitors: number; conversionRate: number; pendingFulfillment: number; lowStock: number; refundRate: number } | null>(null);
  const sellerOrders = orders;
  const validSellerOrders = sellerOrders.filter((order) => order.status !== "已取消");
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
    fetch(`${API_BASE}/api/analytics/seller?days=${analyticsDays}`, { credentials: "include" })
      .then((response) => (response.ok ? response.json() : Promise.reject()))
      .then((payload: { analytics: typeof analytics }) => setAnalytics(payload.analytics))
      .catch(() => undefined);
  }, [analyticsDays]);
  const conversionRate = visitorCount
    ? `${((validSellerOrders.length / visitorCount) * 100).toFixed(1)}%`
    : "0.0%";
  const pendingFulfillmentCount = sellerOrders.filter(
    (order) => order.status === "待发货",
  ).length;
  const productSales = new Map<number, number>();
  for (const order of validSellerOrders) {
    for (const item of order.items) {
      if (data.products.find((product) => product.id === item.productId)?.shopId !== 99)
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
    .sort((left, right) => right.sales - left.sales || right.product.reviews - left.product.reviews)
    .slice(0, 5);
  const inventoryWarnings = sellerProducts
    .filter((product) => product.listed !== false && lowStockCount(product) > 0)
    .sort((left, right) => left.stock - right.stock);
  const displayedRevenue = analytics?.revenue ?? transactionAmount;
  const displayedOrders = analytics?.orders ?? validSellerOrders.length;
  const displayedVisitors = analytics?.visitors ?? visitorCount;
  const displayedConversion = analytics ? `${analytics.conversionRate.toFixed(1)}%` : conversionRate;
  const displayedPending = analytics?.pendingFulfillment ?? pendingFulfillmentCount;
  const displayedLowStock = analytics?.lowStock ?? inventoryWarnings.length;
  const inventoryProduct = sellerProducts.find((product) => product.id === inventoryProductId) || sellerProducts[0];
  const inventorySku = inventoryProduct?.skus?.find((sku) => sku.id === inventorySkuId) || inventoryProduct?.skus?.find((sku) => (sku.status ?? "active") === "active");
  const inventorySearchResults = listedSellerProducts.filter((product) => {
    const keyword = inventorySearch.trim().toLowerCase();
    return !keyword || [product.title, product.catalogId || "", String(product.id)].some((value) => value.toLowerCase().includes(keyword));
  });
  const inventoryListRows = listedSellerProducts.flatMap((product) => (product.skus || []).map((sku) => ({ product, sku }))).filter(({ product, sku }) => {
    const keyword = inventorySearch.trim().toLowerCase();
    const spec = Object.entries(sku.optionValues).map(([name, value]) => `${name}:${value}`).join(" ");
    return !keyword || [product.title, product.catalogId || "", String(product.id), sku.code || "", spec].some((value) => value.toLowerCase().includes(keyword));
  });
  const allVisibleInventorySelected = inventoryListRows.length > 0 && inventoryListRows.every(({ sku }) => inventorySelectedSkuIds.includes(sku.id));
  const selectInventoryProduct = (product: Product) => {
    setInventoryProductId(product.id);
    setInventorySkuId(product.skus?.find((sku) => (sku.status ?? "active") === "active")?.id || "");
    setInventorySearch("");
    setInventorySearchOpen(false);
  };
  const selectInventorySku = (product: Product, sku: ProductSku) => {
    setInventoryProductId(product.id);
    setInventorySkuId(sku.id);
  };
  useEffect(() => {
    if (tab !== "inventory") return;
    const query = inventoryProduct?.catalogId ? `?productId=${encodeURIComponent(inventoryProduct.catalogId)}` : "";
    fetch(`${API_BASE}/api/seller/inventory/adjustments${query}`, { credentials: "include" })
      .then((response) => (response.ok ? response.json() : Promise.reject()))
      .then((payload: { adjustments: InventoryAdjustment[] }) => setInventoryAdjustments(payload.adjustments))
      .catch(() => setInventoryAdjustments([]));
  }, [tab, inventoryProduct?.catalogId]);
  const adjustInventory = async () => {
    if (!inventoryProduct?.catalogId || !inventorySku?.id || !inventoryQuantity)
      return toast("请选择作品、SKU 并填写调整数量");
    const quantity = Number(inventoryQuantity);
    if (!Number.isInteger(quantity) || quantity < 0)
      return toast("库存调整数量必须是非负整数");
    if (!inventoryReason.trim()) return toast("请填写库存调整原因");
    const response = await fetch(`${API_BASE}/api/seller/inventory/adjustments`, {
      method: "POST", credentials: "include", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ productId: inventoryProduct.catalogId, skuId: inventorySku.id, type: inventoryAdjustmentType, quantity, reason: inventoryReason }),
    });
    const payload = (await response.json()) as { product?: Product; error?: string };
    if (!response.ok || !payload.product) return toast(payload.error || "库存调整失败");
    setData((current) => ({ ...current, products: current.products.map((product) => product.catalogId === payload.product!.catalogId ? payload.product! : product) }));
    setInventoryQuantity("");
    setInventoryReason("");
    const history = await fetch(`${API_BASE}/api/seller/inventory/adjustments?productId=${encodeURIComponent(inventoryProduct.catalogId)}`, { credentials: "include" });
    if (history.ok) setInventoryAdjustments(((await history.json()) as { adjustments: InventoryAdjustment[] }).adjustments);
    toast("库存已更新");
  };
  const setInventorySkuStatus = async (sku: ProductSku, status: "active" | "disabled") => {
    const response = await fetch(`${API_BASE}/api/seller/inventory/skus/${encodeURIComponent(sku.id)}/status`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ status }) });
    const payload = (await response.json()) as { product?: Product; error?: string };
    if (!response.ok || !payload.product) return toast(payload.error || "SKU 状态更新失败");
    setData((current) => ({ ...current, products: current.products.map((product) => product.catalogId === payload.product!.catalogId ? payload.product! : product) }));
    toast(status === "active" ? "SKU 已启用" : "SKU 已停用");
  };
  const saveInventoryList = async () => {
    const selectedRows = inventoryListRows.filter(({ sku }) => inventorySelectedSkuIds.includes(sku.id));
    if (!selectedRows.length) return toast("请先勾选需要修改的 SKU");
    if (!inventoryListReason.trim()) return toast("请填写本次盘点原因");
    const updates = selectedRows.flatMap(({ product, sku }) => {
      const nextValue = inventoryRowValues[sku.id];
      if (nextValue === undefined || nextValue === "" || Number(nextValue) === sku.stock) return [];
      const quantity = Number(nextValue);
      return Number.isInteger(quantity) && quantity >= 0 && product.catalogId ? [{ product, sku, quantity }] : [];
    });
    if (!updates.length) return toast("请在已选 SKU 的库存框中输入有效的新库存");
    const changedProducts: Product[] = [];
    const savedSkuIds: string[] = [];
    for (const item of updates) {
      const response = await fetch(`${API_BASE}/api/seller/inventory/adjustments`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ productId: item.product.catalogId, skuId: item.sku.id, type: "set", quantity: item.quantity, reason: inventoryListReason.trim() }) });
      const payload = (await response.json().catch(() => ({}))) as { product?: Product; error?: string };
      if (!response.ok || !payload.product) {
        toast(payload.error || `${item.sku.code || "该 SKU"} 库存保存失败`);
        continue;
      }
      changedProducts.push(payload.product);
      savedSkuIds.push(item.sku.id);
    }
    if (!changedProducts.length) return;
    const productUpdates = new Map(changedProducts.map((product) => [product.catalogId, product]));
    setData((current) => ({ ...current, products: current.products.map((product) => productUpdates.get(product.catalogId) || product) }));
    setInventoryRowValues((current) => {
      const next = { ...current };
      savedSkuIds.forEach((id) => delete next[id]);
      return next;
    });
    setInventorySelectedSkuIds((current) => current.filter((id) => !savedSkuIds.includes(id)));
    setInventoryListReason("");
    toast(`已保存 ${savedSkuIds.length} 个 SKU 的库存`);
  };
  const exportInventory = () => {
    const rows = [["作品", "作品ID", "SKU", "规格", "售价", "可售库存", "状态", "预警阈值"]];
    sellerProducts.forEach((product) => (product.skus || []).forEach((sku) => rows.push([product.title, product.catalogId || "", sku.code || "", Object.entries(sku.optionValues).map(([name, value]) => `${name}:${value}`).join(" / ") || "默认规格", String(sku.price ?? product.price), String(sku.stock), sku.status === "disabled" ? "停用" : "可售", String(product.lowStockThreshold ?? 3)])));
    const csv = `\uFEFF${rows.map((row) => row.map((value) => `"${value.replace(/"/g, '""')}"`).join(",")).join("\n")}`;
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
    const link = document.createElement("a"); link.href = url; link.download = "库存导出.csv"; link.click(); URL.revokeObjectURL(url);
  };
  const uploadMedia = async (data: string, mediaType: "image" | "video") => {
    const response = await fetch(`${API_BASE}/api/media`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ data, mediaType }),
    });
    const payload = (await response.json()) as { url?: string; error?: string };
    if (!response.ok || !payload.url) throw new Error(payload.error || "媒体上传失败");
    return payload.url.startsWith("/") ? `${API_BASE}${payload.url}` : payload.url;
  };
  const normalizeImage = (file: File) =>
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
  const validateProductImage = (file: File) => {
    if (!PRODUCT_IMAGE_TYPES.has(file.type))
      return "图片仅支持 JPG、PNG 或 WebP 格式";
    if (file.size > MAX_PRODUCT_IMAGE_SIZE)
      return "单张图片不能超过 10MB";
    return "";
  };
  const chooseImages = async (files: FileList | null) => {
    const selected = Array.from(files || []);
    const remaining = 10 - form.images.length;
    if (!selected.length) return;
    if (remaining <= 0) return toast("最多只能上传 10 张图片");
    if (selected.length > remaining)
      return toast(`最多还能上传 ${remaining} 张图片`);
    const invalidMessage = selected
      .map(validateProductImage)
      .find(Boolean);
    if (invalidMessage) return toast(invalidMessage);
    try {
      const normalizedImages = await Promise.all(selected.map(normalizeImage));
      const images = await Promise.all(normalizedImages.map((image) => uploadMedia(image, "image")));
      setForm((value) => ({ ...value, images: [...value.images, ...images] }));
    } catch (error) {
      toast(error instanceof Error ? error.message : "图片上传失败");
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
  const chooseVideo = (file?: File) => {
    if (!file) return;
    if (!PRODUCT_VIDEO_TYPES.has(file.type))
      return toast("视频仅支持 MP4、WebM 或 MOV 格式");
    if (file.size > MAX_PRODUCT_VIDEO_SIZE)
      return toast("视频不能超过 50MB");
    const reader = new FileReader();
    reader.onload = () => {
      void uploadMedia(String(reader.result), "video")
        .then((video) => setForm((value) => ({ ...value, video })))
        .catch((error) => toast(error instanceof Error ? error.message : "视频上传失败"));
    };
    reader.onerror = () => toast("无法读取该视频");
    reader.readAsDataURL(file);
  };
  const chooseVariantImage = async (
    variantId: number,
    valueId: number,
    file?: File,
  ) => {
    if (!file) return;
    try {
      const normalizedImage = await normalizeImage(file);
      const image = await uploadMedia(normalizedImage, "image");
      setVariantDrafts((items) =>
        items.map((variant) =>
          variant.id === variantId
            ? {
                ...variant,
                values: variant.values.map((value) =>
                  value.id === valueId ? { ...value, image } : value,
                ),
              }
            : variant,
        ),
      );
    } catch (error) {
      toast(error instanceof Error ? error.message : "图片上传失败");
    }
  };
  const moveImage = (from: number, to: number) => {
    if (from === to) return;
    setForm((value) => {
      const images = [...value.images];
      const [moved] = images.splice(from, 1);
      images.splice(to, 0, moved);
      return { ...value, images };
    });
  };
  const resetProductForm = () => {
    setForm({
      title: "",
      price: "",
      category: "陶艺",
      stock: "10",
      lowStockThreshold: "3",
      description: "",
      images: [],
      video: "",
      seoTags: [],
    });
    setSeoTagInput("");
    setVariantDrafts([]);
    setSkuStocks({});
    setSkuPrices({});
    setSkuCodes({});
    setSkuStatuses({});
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
      "title" | "price" | "category" | "stock" | "lowStockThreshold" | "description" | "images" | "video" | "seoTags" | "variants" | "skus"
    >,
  ) => {
    setForm({
      title: item.title,
      price: item.price,
      category: item.category,
      stock: item.stock,
      lowStockThreshold: item.lowStockThreshold || "3",
      description: item.description,
      images: item.images,
      video: item.video,
      seoTags: item.seoTags || [],
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
    setSkuPrices(Object.fromEntries((item.skus || []).map((sku) => [variantCombinationKey(sku.optionValues), String(sku.price ?? item.price)])));
    setSkuCodes(Object.fromEntries((item.skus || []).map((sku) => [variantCombinationKey(sku.optionValues), sku.code || ""])));
    setSkuStatuses(Object.fromEntries((item.skus || []).map((sku) => [variantCombinationKey(sku.optionValues), sku.status ?? "active"])));
    setShowForm(true);
  };
  const saveDraft = async () => {
    const draft: ProductDraft = {
      id: editingDraftId || Date.now(),
      catalogId: editingDraftCatalogId || undefined,
      title: form.title || "未命名草稿",
      price: form.price,
      category: form.category,
      stock: form.stock,
      lowStockThreshold: form.lowStockThreshold,
      description: form.description,
      images: form.images,
      video: form.video,
      seoTags: form.seoTags,
      variants: collectVariants(),
      skus: collectVariants().length
        ? variantStockCombinations.map((optionValues) => ({
            id: variantCombinationKey(optionValues),
            optionValues,
            stock:
              Number(
                skuStocks[variantCombinationKey(optionValues)] || form.stock,
              ) || 0,
            price: Number(skuPrices[variantCombinationKey(optionValues)] || form.price) || 0,
            code: skuCodes[variantCombinationKey(optionValues)] || "",
            status: skuStatuses[variantCombinationKey(optionValues)] || "active",
          }))
        : [],
      updatedAt: "刚刚",
    };
    const response = await fetch(`${API_BASE}/api/seller/drafts`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ product: draft }),
    });
    const payload = (await response.json()) as { product?: Product; error?: string };
    if (!response.ok || !payload.product) return toast(payload.error || "草稿保存失败");
    const savedDraft = { ...draft, id: payload.product.id, catalogId: payload.product.catalogId };
    setData((current) => ({
      ...current,
      drafts: current.drafts.some((item) => item.id === draft.id)
        ? current.drafts.map((item) => (item.id === draft.id ? savedDraft : item))
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
      lowStockThreshold: String(product.lowStockThreshold ?? 3),
      description: product.description,
      images: product.images || [product.image],
      video: product.video || "",
      seoTags: product.seoTags || [],
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
    if (!form.title.trim() || !form.price || !form.description.trim())
      return toast("请填写作品名称、价格和描述");
    if (characterCount(form.title) > 30)
      return toast("作品名称最多 30 个字");
    if (!form.images.length) return toast("请至少上传 1 张作品图片");
    const sensitiveWord = sensitiveContentWord(
      `${form.title}${form.description}${form.seoTags.join("")}`,
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
      : undefined;
    const p: Product = {
      id: Date.now(),
      catalogId: editingProductCatalogId || editingDraftCatalogId || undefined,
      title: form.title.trim(),
      price: Number(form.price),
      category: form.category,
      stock: skus
        ? skus.filter((sku) => sku.status === "active").reduce((total, sku) => total + sku.stock, 0)
        : Number(form.stock) || 1,
      lowStockThreshold: Math.max(0, Number(form.lowStockThreshold) || 0),
      image:
        form.images[0] ||
        productImages[sellerProducts.length % productImages.length],
      images: form.images.length ? form.images : undefined,
      video: form.video || undefined,
      shopId: 99,
      shop: data.shop.name,
      rating: 5,
      reviews: 0,
      tags: ["新上架", "原创手作"],
      seoTags: form.seoTags,
      publishStatus: "published",
      reviewStatus: "approved",
      custom: true,
      description: form.description,
      material: "手工制作",
      variants: variants.length ? variants : undefined,
      skus,
    };
    const response = await fetch(`${API_BASE}/api/seller/products`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ product: p, status: "published" }),
    });
    const payload = (await response.json()) as { product?: Product; error?: string };
    if (!response.ok || !payload.product) return toast(payload.error || "作品保存失败");
    const savedProduct = payload.product;
    setData((v) => ({
      ...v,
      products: editingProductId
        ? v.products.map((product) =>
            product.id === editingProductId
              ? savedProduct
              : product,
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
  const changeProductStatus = async (product: Product, status: "published" | "unlisted") => {
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
    const payload = (await response.json()) as { product?: Product; error?: string };
    if (!response.ok || !payload.product) return toast(payload.error || "作品状态更新失败");
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
      products: current.products.filter((item) => item.catalogId !== product.catalogId),
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
      body: JSON.stringify({ targetType: "product", targetId: product.catalogId, content: content.trim() }),
    });
    const payload = (await response.json()) as { error?: string };
    toast(response.ok ? "申诉已提交，等待平台复审" : payload.error || "申诉提交失败");
  };
  const applyBulkChanges = async () => {
    const products = listedSellerProducts.filter((product) => selectedProductIds.includes(product.id));
    const productIds = products.map((product) => product.catalogId).filter(Boolean) as string[];
    if (productIds.length !== products.length) return toast("部分作品尚未同步完成");
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
    const payload = (await response.json()) as { products?: Product[]; error?: string };
    if (!response.ok || !payload.products) return toast(payload.error || "批量修改失败");
    const updates = new Map(payload.products.map((product) => [product.catalogId, product]));
    setData((current) => ({
      ...current,
      products: current.products.map((product) => updates.get(product.catalogId) || product),
    }));
    setBulkPrice("");
    setBulkStock("");
    toast("批量修改已保存");
  };
  const saveShop = async () => {
    const response = await fetch(`${API_BASE}/api/seller/shop`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ shop: data.shop }),
    });
    const payload = (await response.json()) as { shop?: Shop; error?: string };
    if (!response.ok || !payload.shop) return toast(payload.error || "店铺设置保存失败");
    setData((current) => ({ ...current, shop: payload.shop! }));
    toast("店铺设置已保存");
  };
  return (
    <div className="studio">
      <div className="studio-side">
        <div className="studio-brand">
          <Store size={22} />
          店主工作台
        </div>
        {(
          [
            ["overview", "概览"],
            ["products", "我的作品"],
            ["inventory", "库存管理"],
            ["orders", "订单管理"],
            ["messages", "买家消息"],
            ["reviews", "评价管理"],
            ["shipping", "运费管理"],
            ["service", "认证、成员与客服"],
            ["promotions", "优惠管理"],
            ["finance", "结算与资金"],
            ["settings", "店铺设置"],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            data-testid={`seller-tab-${id}`}
            className={tab === id ? "active" : ""}
            onClick={() => setTab(id)}
          >
            {id === "overview" ? (
              <Settings2 size={18} />
            ) : id === "products" ? (
              <Package size={18} />
            ) : id === "inventory" ? (
              <SlidersHorizontal size={18} />
            ) : id === "orders" ? (
              <ShoppingBag size={18} />
            ) : id === "messages" ? (
              <MessageCircle size={18} />
            ) : id === "reviews" ? (
              <Star size={18} />
            ) : id === "shipping" ? (
              <Truck size={18} />
            ) : id === "service" ? (
              <UserRound size={18} />
            ) : id === "promotions" ? (
              <CreditCard size={18} />
            ) : id === "finance" ? (
              <CreditCard size={18} />
            ) : (
              <Store size={18} />
            )}{" "}
            {label}
          </button>
        ))}
      </div>
      <div className="studio-main">
        {tab === "overview" && (
          <>
            <div className="studio-title">
              <div>
                <p className="eyebrow">你好，{data.shop.owner}</p>
                <h1>今天也做点有意思的事</h1>
              </div>
              <button
                className="primary"
                onClick={() => {
                  setTab("products");
                  setShowForm(true);
                }}
              >
                <Plus size={18} />
                发布作品
              </button>
            </div>
            <div className="order-filters"><button className={analyticsDays === 7 ? "selected" : ""} onClick={() => setAnalyticsDays(7)}>近 7 天</button><button className={analyticsDays === 30 ? "selected" : ""} onClick={() => setAnalyticsDays(30)}>近 30 天</button></div>
            <div className="metric-grid">
              <Metric
                label="成交额"
                value={money(displayedRevenue)}
                trend={`${displayedOrders} 笔有效订单`}
              />
              <Metric
                label="访客"
                value={displayedVisitors.toLocaleString()}
                trend={`近 ${analyticsDays} 天访问`}
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
                  <button className="text-link" onClick={() => setTab("products")}>
                    管理作品
                  </button>
                </div>
                {hotProducts.length ? (
                  <div className="dashboard-product-list">
                    {hotProducts.map(({ product, sales }, index) => (
                      <button key={product.id} onClick={() => onOpen(product.id)}>
                        <em>{index + 1}</em>
                        <img src={product.image} alt="" />
                        <span>
                          <b>{product.title}</b>
                          <small>{sales} 件成交 · {money(product.price)}</small>
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
                  <button className="text-link" onClick={() => setTab("orders")}>
                    查看订单
                  </button>
                </div>
                <b className="dashboard-emphasis">{pendingFulfillmentCount} 笔</b>
                <p>
                  {pendingFulfillmentCount
                    ? "请及时确认库存并录入物流单号。"
                    : "当前没有等待发货的订单。"}
                </p>
              </section>
              <section className="studio-panel dashboard-panel">
                <div className="panel-head">
                  <h3>库存预警</h3>
                  <button className="text-link" onClick={() => setTab("products")}>
                    调整库存
                  </button>
                </div>
                {inventoryWarnings.length ? (
                  <div className="dashboard-stock-list">
                    {inventoryWarnings.slice(0, 4).map((product) => (
                      <button key={product.id} onClick={() => onOpen(product.id)}>
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
                <h1>我的作品</h1>
                <p>管理你的原创作品与库存</p>
              </div>
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
                  {showForm ? <X size={18} /> : <Plus size={18} />}
                  {showForm ? "取消编辑" : "发布作品"}
                </button>
              </div>
            </div>
            {!showForm && (
              <div className="product-list-tabs" role="tablist" aria-label="作品状态">
                <button
                  className={productListMode === "listed" ? "active" : ""}
                  onClick={() => setProductListMode("listed")}
                >
                  已上架 {listedSellerProducts.length}
                </button>
                <button
                  className={productListMode === "trash" ? "active" : ""}
                  onClick={() => setProductListMode("trash")}
                >
                  回收站 {recycledSellerProducts.length}
                </button>
              </div>
            )}
            {showForm && (
              <section className="studio-panel publish-form">
                <h3>{editingProductId ? "编辑作品" : "发布一件新作品"}</h3>
                <label>
                  作品名称（最多 30 个字）
                  <input
                    value={form.title}
                  onChange={(e) =>
                      setForm({ ...form, title: e.target.value })
                    }
                    placeholder="例如：手作陶瓷香插"
                    maxLength={30}
                  />
                </label>
                <div className="form-split">
                  <label>
                    价格
                    <input
                      type="number"
                      value={form.price}
                      onChange={(e) =>
                        setForm({ ...form, price: e.target.value })
                      }
                      placeholder="0.00"
                    />
                  </label>
                  <label>
                    库存
                    <input
                      type="number"
                      min="0"
                      value={form.stock}
                      onChange={(e) =>
                        setForm({ ...form, stock: e.target.value })
                      }
                    />
                  </label>
                  <label>
                    低库存预警
                    <input
                      type="number"
                      min="0"
                      value={form.lowStockThreshold}
                      onChange={(e) =>
                        setForm({ ...form, lowStockThreshold: e.target.value })
                      }
                    />
                  </label>
                  <label>
                    分类
                    <select
                      value={form.category}
                      onChange={(e) =>
                        setForm({
                          ...form,
                          category: e.target.value as Category,
                        })
                      }
                    >
                      {categories.map((c) => (
                        <option key={c.name}>{c.name}</option>
                      ))}
                    </select>
                  </label>
                </div>
                <div className="upload-grid">
                  {form.video ? (
                    <div className="upload-preview video-preview">
                      <video src={form.video} muted controls />
                      <button
                        type="button"
                        title="移除视频"
                        aria-label="移除视频"
                        onClick={() =>
                          setForm((value) => ({ ...value, video: "" }))
                        }
                      >
                        <X size={15} />
                      </button>
                      <span>视频</span>
                    </div>
                  ) : (
                    <label className="image-upload video-upload">
                      <input
                        type="file"
                        accept="video/*"
                        onChange={(event) => {
                          chooseVideo(event.target.files?.[0]);
                          event.currentTarget.value = "";
                        }}
                      />
                      <span>
                        <Video size={24} />
                        添加视频
                        <small>MP4/WebM/MOV，不超过 50MB</small>
                      </span>
                    </label>
                  )}
                  {form.images.map((image, index) => (
                    <div
                      className={`upload-preview ${dragOverImageIndex === index ? "drag-over" : ""} ${draggedImageIndex === index ? "dragging" : ""}`}
                      key={image}
                      draggable
                      onDragStart={() => setDraggedImageIndex(index)}
                      onDragOver={(event) => {
                        event.preventDefault();
                        setDragOverImageIndex(index);
                      }}
                      onDrop={(event) => {
                        event.preventDefault();
                        if (draggedImageIndex !== null)
                          moveImage(draggedImageIndex, index);
                        setDraggedImageIndex(null);
                        setDragOverImageIndex(null);
                      }}
                      onDragEnd={() => {
                        setDraggedImageIndex(null);
                        setDragOverImageIndex(null);
                      }}
                    >
                      <img src={image} alt={`作品图片 ${index + 1}`} />
                      <button
                        type="button"
                        title="移除图片"
                        aria-label="移除图片"
                        onClick={() =>
                          setForm((value) => ({
                            ...value,
                            images: value.images.filter(
                              (_, imageIndex) => imageIndex !== index,
                            ),
                          }))
                        }
                      >
                        <X size={15} />
                      </button>
                      {index === 0 && <span>主图</span>}
                    </div>
                  ))}
                  {form.images.length < 10 && (
                    <label className="image-upload">
                      <input
                        type="file"
                        accept="image/*"
                        multiple
                        onChange={(event) => {
                          chooseImages(event.target.files);
                          event.currentTarget.value = "";
                        }}
                      />
                      <span>
                        <ImagePlus size={24} />
                        添加图片
                        <small>JPG/PNG/WebP，单张不超过 10MB</small>
                      </span>
                    </label>
                  )}
                </div>
                <div className="seo-tag-editor">
                  <div>
                    <b>搜索标签</b>
                    <small>最多 12 个，每个最多 10 个字</small>
                  </div>
                  <div className="seo-tag-input">
                    <input
                      value={seoTagInput}
                      onChange={(event) => setSeoTagInput(event.target.value)}
                      onKeyDown={(event) => {
                        if (event.key !== "Enter") return;
                        event.preventDefault();
                        addSeoTag();
                      }}
                      placeholder="输入标签后按回车"
                      maxLength={10}
                    />
                    <IconButton
                      icon={Plus}
                      label="添加搜索标签"
                      onClick={addSeoTag}
                      disabled={form.seoTags.length >= 12}
                    />
                  </div>
                  {!!form.seoTags.length && (
                    <div className="seo-tag-list">
                      {form.seoTags.map((tag) => (
                        <span key={tag}>
                          {tag}
                          <button
                            type="button"
                            title={`移除标签 ${tag}`}
                            aria-label={`移除标签 ${tag}`}
                            onClick={() =>
                              setForm((value) => ({
                                ...value,
                                seoTags: value.seoTags.filter((item) => item !== tag),
                              }))
                            }
                          >
                            <X size={14} />
                          </button>
                        </span>
                      ))}
                    </div>
                  )}
                </div>
                <div className="variant-editor">
                  <div>
                    <b>商品规格</b>
                    <small>每个规格值可以上传一张对应图片</small>
                  </div>
                  {variantDrafts.map((variant) => (
                    <div className="variant-draft-wrap" key={variant.id}>
                      <div className="variant-heading">
                        <select
                          value={variant.name}
                          onChange={(event) =>
                            setVariantDrafts((items) =>
                              items.map((item) =>
                                item.id === variant.id
                                  ? { ...item, name: event.target.value }
                                  : item,
                              ),
                            )
                          }
                        >
                          <option value="">选择规格类型</option>
                          <option value="颜色">颜色</option>
                          <option value="尺寸">尺寸</option>
                          <option value="型号">型号</option>
                          <option value="组合">组合</option>
                        </select>
                        <IconButton
                          icon={X}
                          label="删除规格"
                          onClick={() =>
                            setVariantDrafts((items) =>
                              items.filter((item) => item.id !== variant.id),
                            )
                          }
                        />
                      </div>
                      <div className="variant-value-list">
                        {variant.values.map((item, index) => (
                          <div className="variant-value-row" key={item.id}>
                            <input
                              value={item.value}
                              onChange={(event) =>
                                setVariantDrafts((items) =>
                                  items.map((draft) =>
                                    draft.id === variant.id
                                      ? {
                                          ...draft,
                                          values: draft.values.map((value) =>
                                            value.id === item.id
                                              ? { ...value, value: event.target.value }
                                              : value,
                                          ),
                                        }
                                      : draft,
                                  ),
                                )
                              }
                              placeholder={`规格值 ${index + 1}`}
                            />
                            <label className="variant-image-upload" title="上传对应图片">
                              <input
                                type="file"
                                accept="image/*"
                                onChange={(event) => {
                                  chooseVariantImage(
                                    variant.id,
                                    item.id,
                                    event.target.files?.[0],
                                  );
                                  event.currentTarget.value = "";
                                }}
                              />
                              {item.image ? (
                                <img src={item.image} alt="规格值对应图片" />
                              ) : (
                                <ImagePlus size={20} />
                              )}
                            </label>
                            {variant.values.length > 1 && (
                              <button
                                type="button"
                                className="remove-value"
                                onClick={() =>
                                  setVariantDrafts((items) =>
                                    items.map((draft) =>
                                      draft.id === variant.id
                                        ? {
                                            ...draft,
                                            values: draft.values.filter(
                                              (value) => value.id !== item.id,
                                            ),
                                          }
                                        : draft,
                                    ),
                                  )
                                }
                                aria-label="删除规格值"
                                title="删除规格值"
                              >
                                <X size={16} />
                              </button>
                            )}
                          </div>
                        ))}
                      </div>
                      <button
                        type="button"
                        className="continue-add"
                        onClick={() =>
                          setVariantDrafts((items) =>
                            items.map((draft) =>
                              draft.id === variant.id
                                ? {
                                    ...draft,
                                    values: [
                                      ...draft.values,
                                      { id: Date.now(), value: "" },
                                    ],
                                  }
                                : draft,
                            ),
                          )
                        }
                      >
                        继续添加
                      </button>
                    </div>
                  ))}
                  {variantDrafts.length < 3 && (
                    <button
                      type="button"
                      className="add-variant"
                      onClick={() =>
                        setVariantDrafts((items) => [
                          ...items,
                          {
                            id: Date.now(),
                            name: "",
                            values: [{ id: Date.now() + 1, value: "" }],
                          },
                        ])
                      }
                    >
                      <Plus size={16} />
                      添加规格
                    </button>
                  )}
                </div>
                {hasCompleteVariants && (
                  <section className="sku-stock-editor">
                    <div>
                      <b>规格组合库存</b>
                      <small>未填写时使用上方默认库存</small>
                    </div>
                    <div className="sku-stock-list sku-detail-list">
                      {variantStockCombinations.map((optionValues) => {
                        const key = variantCombinationKey(optionValues);
                        return (
                          <div className="sku-detail-row" key={key}>
                            <span>
                              {Object.entries(optionValues)
                                .map(([name, value]) => `${name}: ${value}`)
                                .join(" · ")}
                            </span>
                            <input value={skuCodes[key] ?? ""} maxLength={40} onChange={(event) => setSkuCodes((value) => ({ ...value, [key]: event.target.value }))} placeholder="SKU 编码" aria-label={`${key} SKU 编码`} />
                            <input type="number" min="0" step="0.01" value={skuPrices[key] ?? form.price} onChange={(event) => setSkuPrices((value) => ({ ...value, [key]: event.target.value }))} placeholder="售价" aria-label={`${key} 售价`} />
                            <input type="number" min="0" value={skuStocks[key] ?? form.stock} onChange={(event) => setSkuStocks((stocks) => ({ ...stocks, [key]: event.target.value }))} aria-label={`${key}库存`} />
                            <label className="sku-status-toggle"><input type="checkbox" checked={(skuStatuses[key] ?? "active") === "active"} onChange={(event) => setSkuStatuses((value) => ({ ...value, [key]: event.target.checked ? "active" : "disabled" }))} />可售</label>
                          </div>
                        );
                      })}
                    </div>
                  </section>
                )}
                <label>
                  作品描述
                  <textarea
                    value={form.description}
                    onChange={(event) =>
                      setForm({ ...form, description: event.target.value })
                    }
                    placeholder="介绍作品的灵感、工艺、尺寸或适用场景..."
                    maxLength={300}
                  />
                </label>
                <div className="publish-actions">
                  <button className="secondary" type="button" onClick={saveDraft}>
                    保存草稿
                  </button>
                  <button className="primary" onClick={addProduct}>
                    {editingProductId ? "保存修改" : "确认发布"}
                  </button>
                </div>
              </section>
            )}
            {!showForm && (
              <>
                {productListMode === "listed" && !!listedSellerProducts.length && (
                  <section className="studio-panel bulk-editor">
                    <label className="select-all">
                      <input
                        type="checkbox"
                        checked={
                          selectedProductIds.length === listedSellerProducts.length
                        }
                        onChange={(event) =>
                          setSelectedProductIds(
                            event.target.checked
                              ? listedSellerProducts.map((product) => product.id)
                              : [],
                          )
                        }
                      />
                      全选
                    </label>
                    <div>
                      <b>批量修改</b>
                      <span>已选 {selectedProductIds.length} 件作品</span>
                    </div>
                    <input
                      type="number"
                      value={bulkPrice}
                      onChange={(event) => setBulkPrice(event.target.value)}
                      placeholder="统一价格"
                    />
                    <input
                      type="number"
                      value={bulkStock}
                      onChange={(event) => setBulkStock(event.target.value)}
                      placeholder="统一库存"
                    />
                    <button
                      className="secondary"
                      disabled={
                        !selectedProductIds.length ||
                        (!bulkPrice && !bulkStock)
                      }
                      onClick={() => void applyBulkChanges()}
                    >
                      应用修改
                    </button>
                  </section>
                )}
                <div className="studio-product-list">
                  {displayedSellerProducts.map((p) => (
                    <article className="studio-product-row" key={p.id}>
                      {productListMode === "listed" ? (
                        <input
                          type="checkbox"
                          checked={selectedProductIds.includes(p.id)}
                          onChange={() =>
                            setSelectedProductIds((ids) =>
                              ids.includes(p.id)
                                ? ids.filter((id) => id !== p.id)
                                : [...ids, p.id],
                            )
                          }
                          aria-label={`选择${p.title}`}
                        />
                      ) : (
                        <span className="trash-marker">已下架</span>
                      )}
                      <div className="product-preview">
                        <button className="product-preview-image" onClick={() => onOpen(p.id)} aria-label={`查看${p.title}`}>
                          <img src={p.image} alt="" />
                        </button>
                        <div className="product-preview-info">
                          <button className="product-title-link" onClick={() => onOpen(p.id)}>{p.title}</button>
                          <small>
                            {productListMode === "trash" ? "已下架" : "已发布"}
                            {productListMode === "listed" && ` · ${p.reviewStatus === "approved" ? "自动审核通过" : p.reviewStatus === "rejected" ? "审核未通过" : "审核中"}`}
                            {productListMode === "listed" && lowStockCount(p) > 0 && (
                              <em className="stock-warning">
                                · {lowStockCount(p)} 个低库存规格
                              </em>
                            )}
                          </small>
                        </div>
                        <span className="product-price-stock">
                          <strong>{money(p.price)}</strong>
                          <small>库存 {p.stock} 件</small>
                        </span>
                      </div>
                      <div className="product-row-actions">
                        {productListMode === "listed" ? (
                          <>
                            <button onClick={() => editProduct(p)}>编辑</button>
                            <button
                              onClick={() => {
                                void changeProductStatus(p, "unlisted");
                                setSelectedProductIds((ids) => ids.filter((id) => id !== p.id));
                              }}
                            >
                              下架
                            </button>
                          </>
                        ) : (
                          <>
                            <button
                              onClick={() => void changeProductStatus(p, "published")}
                            >
                              上架
                            </button>
                            {p.reviewStatus === "rejected" && (
                              <button onClick={() => void appealProduct(p)}>申诉</button>
                            )}
                            <button
                              className="danger"
                              onClick={() => void removeProduct(p)}
                            >
                              删除
                            </button>
                          </>
                        )}
                      </div>
                    </article>
                  ))}
                  {!displayedSellerProducts.length && (
                    <Empty
                      title={productListMode === "trash" ? "回收站还是空的" : "还没有作品"}
                      text={
                        productListMode === "trash"
                          ? "下架的作品会暂存在这里。"
                          : "发布你的第一件原创手作吧。"
                      }
                      action={productListMode === "trash" ? "查看已上架作品" : "发布作品"}
                      onAction={() =>
                        productListMode === "trash"
                          ? setProductListMode("listed")
                          : setShowForm(true)
                      }
                    />
                  )}
                </div>
                {!!data.drafts.length && (
                  <section className="studio-panel draft-list">
                    <div className="panel-head">
                      <h3>草稿箱</h3>
                      <span>{data.drafts.length} 份草稿</span>
                    </div>
                    {data.drafts.map((draft) => (
                      <button
                        key={draft.id}
                        onClick={() => {
                          setEditingProductId(null);
                          setEditingProductCatalogId(null);
                          setEditingDraftId(draft.id);
                          setEditingDraftCatalogId(draft.catalogId || null);
                          loadProductForm(draft);
                        }}
                      >
                        <span>
                          <b>{draft.title}</b>
                          <small>保存于 {draft.updatedAt}</small>
                        </span>
                        <span>继续编辑</span>
                      </button>
                    ))}
                  </section>
                )}
              </>
            )}
          </>
        )}
        {tab === "inventory" && (
          <>
            <div className="studio-title"><div><h1>库存管理</h1><p>按 SKU 调整可售库存，并保留每一次变更记录</p></div><button className="secondary" onClick={exportInventory}>导出库存</button></div>
            {inventoryProduct ? <><section className="studio-panel inventory-list-panel"><div className="panel-head"><div><h3>SKU 库存列表</h3><p>勾选 SKU 后可直接录入盘点库存并批量保存。</p></div><span>{inventoryListRows.length} 个 SKU</span></div><div className="inventory-list-toolbar"><label className="inventory-list-search"><Search size={16} /><input value={inventorySearch} onChange={(event) => setInventorySearch(event.target.value)} placeholder="搜索作品、SKU 或规格" /></label><input value={inventoryListReason} maxLength={120} onChange={(event) => setInventoryListReason(event.target.value)} placeholder="批量盘点原因（必填）" /><button className="secondary" disabled={!inventorySelectedSkuIds.length} onClick={() => void saveInventoryList()}>保存已选 {inventorySelectedSkuIds.length || ""}</button></div><div className="inventory-list-head"><label><input type="checkbox" checked={allVisibleInventorySelected} onChange={() => setInventorySelectedSkuIds((current) => allVisibleInventorySelected ? current.filter((id) => !inventoryListRows.some(({ sku }) => sku.id === id)) : Array.from(new Set([...current, ...inventoryListRows.map(({ sku }) => sku.id)])))} />全选</label><span>作品</span><span>规格 / SKU</span><span>售价</span><span>库存</span><span>状态</span><span>操作</span></div><div className="inventory-list">{inventoryListRows.map(({ product, sku }) => { const spec = Object.keys(sku.optionValues).length ? Object.entries(sku.optionValues).map(([name, value]) => `${name}: ${value}`).join(" · ") : "默认规格"; const isLowStock = sku.stock > 0 && sku.stock < 10; const inventoryStatus = sku.stock === 0 ? "售罄" : sku.stock < 10 ? "紧张" : "可售"; return <article key={sku.id} className={`${inventorySku?.id === sku.id ? "selected" : ""} ${isLowStock ? "low-stock" : ""}`}><label className="inventory-row-check"><input type="checkbox" checked={inventorySelectedSkuIds.includes(sku.id)} onChange={() => setInventorySelectedSkuIds((current) => current.includes(sku.id) ? current.filter((id) => id !== sku.id) : [...current, sku.id])} /><span className="sr-only">选择 {product.title}</span></label><button type="button" className="inventory-row-product" onClick={() => selectInventorySku(product, sku)}><img src={product.image} alt="" /><span><b>{product.title}</b><small>ID：{product.catalogId || product.id}</small></span></button><span className="inventory-row-sku"><b>{spec}</b><small>{sku.code || "未编码"}</small></span><span className="inventory-row-price">{money(sku.price ?? product.price)}</span><label className="inventory-row-stock"><input type="number" min="0" step="1" value={inventoryRowValues[sku.id] ?? String(sku.stock)} onChange={(event) => setInventoryRowValues((current) => ({ ...current, [sku.id]: event.target.value }))} /></label><span className={`inventory-row-status ${inventoryStatus === "售罄" ? "sold-out" : inventoryStatus === "紧张" ? "tight" : "available"}`}>{inventoryStatus}</span><button type="button" className="text-link inventory-row-detail" onClick={() => selectInventorySku(product, sku)}>调整</button></article>; })}{!inventoryListRows.length && <p className="inventory-list-empty">没有匹配的 SKU。</p>}</div></section><div className="inventory-layout inventory-detail-layout"><section className="studio-panel inventory-adjustment-panel"><div className="panel-head"><h3>单个 SKU 调整</h3></div><div className="inventory-selected-product"><img src={inventoryProduct.image} alt="" /><span><small>当前作品</small><b>{inventoryProduct.title}</b></span></div><div className="inventory-summary"><span>作品可售库存</span><b>{inventoryProduct.stock}</b><small>预警阈值：{inventoryProduct.lowStockThreshold ?? 3}</small>{inventorySku && <small>当前 SKU：{inventorySku.code || "未编码"} · {money(inventorySku.price ?? inventoryProduct.price)} · {inventorySku.status === "disabled" ? "已停用" : "可售"}</small>}</div><label>SKU<select value={inventorySku?.id || ""} onChange={(event) => setInventorySkuId(event.target.value)}>{(inventoryProduct.skus || []).map((sku) => <option key={sku.id} value={sku.id}>{Object.keys(sku.optionValues).length ? Object.entries(sku.optionValues).map(([name, value]) => `${name}: ${value}`).join(" · ") : "默认规格"}（{sku.status === "disabled" ? "已停用" : `现货 ${sku.stock}`}）</option>)}</select></label>{inventorySku && <button className="secondary" onClick={() => void setInventorySkuStatus(inventorySku, inventorySku.status === "disabled" ? "active" : "disabled")}>{inventorySku.status === "disabled" ? "启用当前 SKU" : "停用当前 SKU"}</button>}<div className="inventory-form-row"><label>操作<select value={inventoryAdjustmentType} onChange={(event) => setInventoryAdjustmentType(event.target.value as typeof inventoryAdjustmentType)}><option value="increase">入库增加</option><option value="decrease">出库减少</option><option value="set">盘点设定</option></select></label><label>数量<input type="number" min="0" step="1" value={inventoryQuantity} onChange={(event) => setInventoryQuantity(event.target.value)} /></label></div><label>调整原因<input maxLength={120} value={inventoryReason} onChange={(event) => setInventoryReason(event.target.value)} placeholder="如：到货补充、盘点修正" /></label><button className="primary" onClick={() => void adjustInventory()}>确认调整</button></section><section className="studio-panel inventory-history-panel"><div className="panel-head"><h3>库存调整记录</h3><span>{inventoryAdjustments.length} 条</span></div>{inventoryAdjustments.length ? <div className="inventory-history-list">{inventoryAdjustments.map((item) => { const sku = inventoryProduct.skus?.find((value) => value.id === item.skuId); const label = sku && Object.keys(sku.optionValues).length ? Object.entries(sku.optionValues).map(([name, value]) => `${name}: ${value}`).join(" · ") : "默认规格"; return <article key={item.id}><div><b>{label}</b><small>{item.reason || "未填写原因"} · {item.createdAt}</small></div><span>{item.type === "increase" ? "+" : item.type === "decrease" ? "-" : "="}{item.type === "decrease" ? item.before - item.after : item.type === "increase" ? item.after - item.before : item.after} <em>{item.before} → {item.after}</em></span></article>; })}</div> : <p>暂无该作品的库存调整记录。</p>}</section></div></> : <Empty title="暂无作品" text="发布作品后即可管理 SKU 库存。" action="发布作品" onAction={() => { setTab("products"); setShowForm(true); }} />}
          </>
        )}
        {tab === "orders" && (
          <>
            <div className="studio-title">
              <div>
                <h1>订单管理</h1>
                <p>处理买家的订单与发货</p>
              </div>
            </div>
            <section className="studio-panel">
              {sellerOrders.length ? (
                sellerOrders.map((o) => (
                  <div className="seller-order" key={o.id}>
                    <div className="seller-order-summary">
                      <div className="seller-order-summary-head">
                        <b>{o.id}</b>
                        <StatusPill status={o.status} className="seller-order-status" />
                      </div>
                      <small>{money(o.amount)}</small>
                    </div>
                    <div className="seller-order-actions">
                      {o.status === "待发货" ? (
                        <button data-testid={`seller-ship-${o.id}`} className="primary" onClick={() => setShipmentOrder(o)}>
                          填写发货信息
                        </button>
                      ) : (
                        <>
                          <button className="secondary" onClick={() => onShipping(o.id)}>查看物流</button>
                          {o.shipment && <button className="secondary" onClick={() => setShipmentEventOrder(o)}>更新物流</button>}
                        </>
                      )}
                    </div>
                    <div className="seller-order-products">
                      {o.items.map((item) => {
                        const product = data.products.find((value) => value.id === item.productId);
                        return (
                          <div className="seller-order-product" key={`${o.id}-${item.catalogId || item.productId}-${JSON.stringify(item.variants || {})}`}>
                            {item.image || product?.image ? <img src={item.image || product?.image} alt="" /> : <span className="seller-order-image-placeholder" />}
                            <span>
                              <b>{item.title || product?.title || "作品"}</b>
                              <small>
                                数量 {item.quantity}
                                {Object.keys(item.variants || {}).length > 0 && ` · ${Object.entries(item.variants || {}).map(([name, value]) => `${name}: ${value}`).join(" · ")}`}
                              </small>
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                ))
              ) : (
                <p>目前没有来自你店铺的订单。</p>
              )}
            </section>
            {shipmentOrder && (
              <ShipmentForm
                order={shipmentOrder}
                onCancel={() => setShipmentOrder(null)}
                onSubmit={async (draft) => {
                  if (await onShip(shipmentOrder.id, draft)) setShipmentOrder(null);
                }}
              />
            )}
            {shipmentEventOrder && (
              <ShipmentEventForm
                order={shipmentEventOrder}
                onCancel={() => setShipmentEventOrder(null)}
                onSubmit={async (label, detail) => {
                  if (await onAddShipmentEvent(shipmentEventOrder.id, label, detail)) setShipmentEventOrder(null);
                }}
              />
            )}
            <section className="studio-panel after-sale-panel">
              <div className="panel-head">
                <h3>售后申请</h3>
                <span>{afterSales.length} 条待处理记录</span>
              </div>
              {afterSales.length ? (
                afterSales.map((request) => (
                  <div className="after-sale-row" key={request.id}>
                    <span>
                      <b>{request.type} · {request.orderId}</b>
                      <small>{request.reason} · {request.createdAt}</small>
                      <small>退款金额 {money(request.amount || 0)}</small>
                      {!!request.evidence?.length && <span className="after-sale-evidence">{request.evidence.map((image) => <img key={image} src={image} alt="售后凭证" />)}</span>}
                      {request.sellerResponse && <small>处理说明：{request.sellerResponse}</small>}
                    </span>
                    <StatusPill status={request.status as OrderStatus} />
                    {request.status === "待处理" && (
                      <div>
                        <button
                          className="secondary"
                          onClick={() => setAfterSaleDecision({ request, action: "reject" })}
                        >
                          拒绝
                        </button>
                        <button
                          className="primary"
                          onClick={() => setAfterSaleDecision({ request, action: "approve" })}
                        >
                          {request.type === "退货退款" ? "同意退货" : "同意退款"}
                        </button>
                      </div>
                    )}
                    {request.status === "待收货" && (
                      <button className="primary" onClick={() => setAfterSaleDecision({ request, action: "receive" })}>确认收到退货</button>
                    )}
                  </div>
                ))
              ) : (
                <p>暂时没有售后申请。</p>
              )}
            </section>
            {afterSaleDecision && (
              <AfterSaleDecisionForm
                key={`${afterSaleDecision.request.id}-${afterSaleDecision.action}`}
                request={afterSaleDecision.request}
                action={afterSaleDecision.action}
                onCancel={() => setAfterSaleDecision(null)}
                onSubmit={async (response) => {
                  const completed = afterSaleDecision.action === "receive"
                    ? await onReceiveReturn(afterSaleDecision.request.id, response)
                    : await onResolveAfterSale(afterSaleDecision.request.id, afterSaleDecision.action, response);
                  if (completed) setAfterSaleDecision(null);
                }}
              />
            )}
          </>
        )}
        {tab === "messages" && (
          <Messages role="seller" embedded />
        )}
        {tab === "reviews" && (
          <>
            <div className="studio-title"><div><h1>评价管理</h1><p>查看买家反馈并回复</p></div></div>
            <section className="studio-panel review-manager">
              {reviews.length ? reviews.map((review) => (
                <article key={review.id}>
                  <b>{"★".repeat(review.rating)} <small>订单 {review.orderId}</small></b>
                  <p>{review.content}</p>
                  {!!review.images?.length && <div className="review-images">{review.images.map((image) => <img key={image} src={image} alt="评价图片" />)}</div>}
                  {review.followup && <p className="review-followup">追评：{review.followup}</p>}
                  {review.sellerReply ? (
                    <span>店主回复：{review.sellerReply}</span>
                  ) : replyingReviewId === review.id ? (
                    <form
                      className="seller-review-reply-form"
                      onSubmit={async (event) => {
                        event.preventDefault();
                        if (!reviewReply.trim()) return;
                        if (await onReplyReview(review.id, reviewReply.trim())) {
                          setReplyingReviewId(null);
                          setReviewReply("");
                        }
                      }}
                    >
                      <textarea value={reviewReply} maxLength={500} placeholder="回复买家的评价" onChange={(event) => setReviewReply(event.target.value)} />
                      <div>
                        <button className="secondary" type="button" onClick={() => { setReplyingReviewId(null); setReviewReply(""); }}>取消</button>
                        <button className="primary" type="submit" disabled={!reviewReply.trim()}>发送回复</button>
                      </div>
                    </form>
                  ) : (
                    <button
                      className="text-link"
                      onClick={() => {
                        setReplyingReviewId(review.id);
                        setReviewReply("");
                      }}
                    >
                      回复评价
                    </button>
                  )}
                </article>
              )) : <p>暂时没有买家评价。</p>}
            </section>
          </>
        )}
        {tab === "finance" && <FinanceCenter toast={toast} />}
        {tab === "shipping" && (
          <>
            <div className="studio-title">
              <div>
                <h1>运费管理</h1>
                <p>配置发货地与店铺配送规则</p>
              </div>
            </div>
            <section className="studio-panel settings-form operations-form">
              <label>
                发货地
                <input
                  value={data.shop.shippingOrigin || ""}
                  placeholder="例如：浙江省杭州市西湖区"
                  onChange={(event) =>
                    setData((value) => ({
                      ...value,
                      shop: { ...value.shop, shippingOrigin: event.target.value },
                    }))
                  }
                />
              </label>
              <div className="operation-settings">
                <div>
                  <b>运费模板</b>
                  <small>设置默认配送规则</small>
                </div>
                <div className="form-split">
                  <label>
                    模板名称
                    <input
                      value={data.shop.shippingTemplate?.name || "标准快递"}
                      onChange={(event) =>
                        setData((value) => ({
                          ...value,
                          shop: {
                            ...value.shop,
                            shippingTemplate: {
                              name: event.target.value,
                              firstFee: value.shop.shippingTemplate?.firstFee || 0,
                              additionalFee: value.shop.shippingTemplate?.additionalFee || 0,
                              freeShippingThreshold: value.shop.shippingTemplate?.freeShippingThreshold,
                            },
                          },
                        }))
                      }
                    />
                  </label>
                  <label>
                    首件运费
                    <input
                      type="number"
                      value={data.shop.shippingTemplate?.firstFee ?? 0}
                      onChange={(event) =>
                        setData((value) => ({
                          ...value,
                          shop: {
                            ...value.shop,
                            shippingTemplate: {
                              name: value.shop.shippingTemplate?.name || "标准快递",
                              firstFee: Number(event.target.value) || 0,
                              additionalFee: value.shop.shippingTemplate?.additionalFee || 0,
                              freeShippingThreshold: value.shop.shippingTemplate?.freeShippingThreshold,
                            },
                          },
                        }))
                      }
                    />
                  </label>
                  <label>
                    续件运费
                    <input
                      type="number"
                      value={data.shop.shippingTemplate?.additionalFee ?? 0}
                      onChange={(event) =>
                        setData((value) => ({
                          ...value,
                          shop: {
                            ...value.shop,
                            shippingTemplate: {
                              name: value.shop.shippingTemplate?.name || "标准快递",
                              firstFee: value.shop.shippingTemplate?.firstFee || 0,
                              additionalFee: Number(event.target.value) || 0,
                              freeShippingThreshold: value.shop.shippingTemplate?.freeShippingThreshold,
                            },
                          },
                        }))
                      }
                    />
                  </label>
                </div>
              </div>
              <button className="primary" onClick={() => void saveShop()}>
                保存更改
              </button>
            </section>
          </>
        )}
        {tab === "service" && (
          <>
            <div className="studio-title">
              <div>
                <h1>认证、成员与客服</h1>
                <p>管理店铺认证、成员权限与客服工单</p>
              </div>
            </div>
            <SellerServiceManagement shopId={analyticsShopId} />
            <SellerActivityOperations shopId={analyticsShopId} />
          </>
        )}
        {tab === "promotions" && (
          <>
            <div className="studio-title">
              <div>
                <h1>优惠管理</h1>
                <p>创建和管理店铺满减优惠</p>
              </div>
            </div>
            <section className="studio-panel settings-form promotions-form">
              <div className="coupon-editor">
                <input
                  type="number"
                  value={couponDraft.threshold}
                  onChange={(event) =>
                    setCouponDraft({ ...couponDraft, threshold: event.target.value })
                  }
                  placeholder="满多少"
                />
                <input
                  type="number"
                  value={couponDraft.discount}
                  onChange={(event) =>
                    setCouponDraft({ ...couponDraft, discount: event.target.value })
                  }
                  placeholder="减多少"
                />
                <button
                  type="button"
                  className="secondary"
                  onClick={() => {
                    if (!couponDraft.threshold || !couponDraft.discount)
                      return toast("请填写满减金额");
                    setData((value) => ({
                      ...value,
                      shop: {
                        ...value.shop,
                        coupons: [
                          ...(value.shop.coupons || []),
                          {
                            id: Date.now(),
                            threshold: Number(couponDraft.threshold),
                            discount: Number(couponDraft.discount),
                          },
                        ],
                      },
                    }));
                    setCouponDraft({ threshold: "", discount: "" });
                  }}
                >
                  添加优惠
                </button>
              </div>
              {!!data.shop.coupons?.length ? (
                <div className="coupon-list">
                  {data.shop.coupons.map((coupon) => (
                    <span key={coupon.id}>
                      满 {money(coupon.threshold)} 减 {money(coupon.discount)}
                      <button
                        type="button"
                        title={`删除满 ${money(coupon.threshold)} 减 ${money(coupon.discount)}`}
                        aria-label={`删除满 ${money(coupon.threshold)} 减 ${money(coupon.discount)}`}
                        onClick={() =>
                          setData((value) => ({
                            ...value,
                            shop: {
                              ...value.shop,
                              coupons: (value.shop.coupons || []).filter(
                                (item) => item.id !== coupon.id,
                              ),
                            },
                          }))
                        }
                      >
                        <X size={14} />
                      </button>
                    </span>
                  ))}
                </div>
              ) : (
                <p>还没有创建优惠活动。</p>
              )}
            </section>
          </>
        )}
        {tab === "settings" && (
          <>
            <div className="studio-title">
              <div>
                <h1>店铺设置</h1>
                <p>更新你的店铺介绍</p>
              </div>
            </div>
            <section className="studio-panel settings-form">
              <div className="shop-media-settings" style={{ display: "grid", gridTemplateColumns: "180px minmax(260px, 480px)", gap: 22, alignItems: "end" }}>
                <label>
                  <span>店铺头像</span>
                  <input
                    type="file"
                    accept="image/*"
                    onChange={(event) => {
                      chooseShopImage("avatar", event.target.files?.[0]);
                      event.currentTarget.value = "";
                    }}
                  />
                  <img src={data.shop.avatar} alt="店铺头像" />
                </label>
                <label>
                  <span>店铺横幅</span>
                  <input
                    type="file"
                    accept="image/*"
                    onChange={(event) => {
                      chooseShopImage("banner", event.target.files?.[0]);
                      event.currentTarget.value = "";
                    }}
                  />
                  <img src={data.shop.banner} alt="店铺横幅" />
                </label>
              </div>
              <label>
                店铺名称
                <input
                  value={data.shop.name}
                  onChange={(e) =>
                    setData((v) => ({
                      ...v,
                      shop: { ...v.shop, name: e.target.value },
                    }))
                  }
                />
              </label>
              <div className="form-split">
                <label>
                  营业状态
                  <select
                    value={data.shop.status || "active"}
                    onChange={(event) =>
                      setData((value) => ({
                        ...value,
                        shop: {
                          ...value.shop,
                          status: event.target.value as "active" | "paused",
                        },
                      }))
                    }
                  >
                    <option value="active">营业中</option>
                    <option value="paused">暂休中</option>
                  </select>
                </label>
              </div>
              <label>
                店铺介绍
                <textarea
                  value={data.shop.description}
                  onChange={(e) =>
                    setData((v) => ({
                      ...v,
                      shop: { ...v.shop, description: e.target.value },
                    }))
                  }
                />
              </label>
              <section className="operation-settings featured-selector">
                <div>
                  <b>店铺首页推荐</b>
                  <small>从已上架作品中选择最多 6 件</small>
                </div>
                {listedSellerProducts.map((product) => (
                  <label key={product.id}>
                    <input
                      type="checkbox"
                      checked={data.shop.featuredProductIds?.includes(product.id) || false}
                      onChange={(event) =>
                        setData((value) => {
                          const featured = value.shop.featuredProductIds || [];
                          const next = event.target.checked
                            ? [...featured, product.id].slice(0, 6)
                            : featured.filter((id) => id !== product.id);
                          return { ...value, shop: { ...value.shop, featuredProductIds: next } };
                        })
                      }
                    />
                    {product.title}
                  </label>
                ))}
              </section>
              <button className="primary" onClick={() => void saveShop()}>
                保存更改
              </button>
            </section>
          </>
        )}
      </div>
    </div>
  );
}

function ServiceAutomationOperations() {
  type Rule = { id: string; name: string; keywords: string[]; priority: "low" | "normal" | "high" | "urgent"; route: "shop" | "platform"; replyTemplate?: string; enabled: boolean; sortOrder: number };
  const [rules, setRules] = useState<Rule[]>([]);
  const [draft, setDraft] = useState({ id: "", name: "", keywords: "", priority: "normal" as Rule["priority"], route: "shop" as Rule["route"], replyTemplate: "", sortOrder: "100" });
  const [notice, setNotice] = useState("");
  const load = async () => { const response = await fetch(`${API_BASE}/api/admin/service-automation`, { credentials: "include" }); const payload = await response.json().catch(() => ({})) as { rules?: Rule[]; error?: string }; if (!response.ok) return setNotice(payload.error || "客服自动化规则加载失败"); setRules(payload.rules || []); };
  useEffect(() => { void load(); }, []);
  const stepUp = async (action: (ticket: string) => Promise<void>) => { const request = await fetch(`${API_BASE}/api/auth/request-admin-step-up`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: "{}" }); const issue = await request.json().catch(() => ({})) as { developmentCode?: string; error?: string }; if (!request.ok) return setNotice(issue.error || "无法请求二次验证"); const code = window.prompt(`请输入二次验证码${issue.developmentCode ? `（开发验证码：${issue.developmentCode}）` : ""}`); if (!code) return; const confirmation = await fetch(`${API_BASE}/api/auth/confirm-admin-step-up`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ code }) }); const verified = await confirmation.json().catch(() => ({})) as { ticket?: string; error?: string }; if (!confirmation.ok || !verified.ticket) return setNotice(verified.error || "二次验证失败"); await action(verified.ticket); };
  const save = (enabled = true, value = draft) => void stepUp(async (ticket) => { const keywords = value.keywords.split(/[，,\n]/).map((item) => item.trim()).filter(Boolean); const response = await fetch(`${API_BASE}/api/admin/service-automation`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json", "X-Admin-Step-Up": ticket }, body: JSON.stringify({ ...value, keywords, sortOrder: Number(value.sortOrder), enabled }) }); const payload = await response.json().catch(() => ({})) as { id?: string; error?: string }; if (!response.ok) return setNotice(payload.error || "规则保存失败"); setNotice("客服自动化规则已保存"); setDraft({ id: "", name: "", keywords: "", priority: "normal", route: "shop", replyTemplate: "", sortOrder: "100" }); void load(); });
  return <section className="studio-panel search-operations"><div className="panel-head"><h2>客服自动化</h2><button className="secondary" onClick={() => void load()}>刷新</button></div>{notice && <p className="auth-error">{notice}</p>}<div className="admin-operation-grid"><div><h3>{draft.id ? "编辑自动化规则" : "新建自动化规则"}</h3><input value={draft.name} maxLength={80} onChange={(event) => setDraft({ ...draft, name: event.target.value })} placeholder="规则名称" /><input value={draft.keywords} maxLength={600} onChange={(event) => setDraft({ ...draft, keywords: event.target.value })} placeholder="命中关键词，使用逗号分隔" /><div className="campaign-rule"><select value={draft.priority} onChange={(event) => setDraft({ ...draft, priority: event.target.value as Rule["priority"] })}><option value="low">低优先级</option><option value="normal">普通</option><option value="high">高优先级</option><option value="urgent">紧急</option></select><select value={draft.route} onChange={(event) => setDraft({ ...draft, route: event.target.value as Rule["route"] })}><option value="shop">优先路由店铺</option><option value="platform">路由平台客服</option></select><input type="number" min="1" max="9999" value={draft.sortOrder} onChange={(event) => setDraft({ ...draft, sortOrder: event.target.value })} placeholder="优先顺序" /></div><textarea value={draft.replyTemplate} maxLength={1000} onChange={(event) => setDraft({ ...draft, replyTemplate: event.target.value })} placeholder="自动回复（可选，可使用 {subject}）" /><button className="primary" disabled={!draft.name.trim() || !draft.keywords.trim()} onClick={() => save()}>保存规则</button></div><div><h3>已配置规则</h3><div className="admin-operation-list">{rules.map((rule) => { const value = { id: rule.id, name: rule.name, keywords: rule.keywords.join("，"), priority: rule.priority, route: rule.route, replyTemplate: rule.replyTemplate || "", sortOrder: String(rule.sortOrder) }; return <div key={rule.id}><span><b>{rule.name}</b> · {rule.keywords.join("、")}<small>{rule.priority} · {rule.route === "platform" ? "平台客服" : "店铺客服"} · 顺序 {rule.sortOrder}{rule.replyTemplate ? " · 自动回复" : ""}</small></span><button className="secondary" onClick={() => setDraft(value)}>编辑</button><button className="secondary" onClick={() => save(!rule.enabled, value)}>{rule.enabled ? "停用" : "启用"}</button></div>; })}{!rules.length && <p>暂无自动化规则</p>}</div></div></div></section>;
}

function SearchOperations() {
  type Kind = "synonym" | "correction" | "recommendation" | "zero_result";
  type Rule = { id: string; source: string; target?: string | string[]; message?: string; productId?: string | null; productTitle?: string | null; weight?: number; enabled: boolean };
  type Payload = { days: number; rules: { synonyms: Rule[]; corrections: Rule[]; recommendations: Rule[]; zeroResults: Rule[] }; summary: { searches: number; zeroResults: number; corrections: number; zeroRate: number }; terms: { keyword: string; searches: number; zeroResults: number; corrections: number }[]; zeroTerms: { keyword: string; searches: number }[] };
  const [data, setData] = useState<Payload | null>(null);
  const [days, setDays] = useState<7 | 30>(30);
  const [kind, setKind] = useState<Kind>("synonym");
  const [source, setSource] = useState("");
  const [target, setTarget] = useState("");
  const [productId, setProductId] = useState("");
  const [weight, setWeight] = useState("100");
  const [notice, setNotice] = useState("");
  const load = async () => { const response = await fetch(`${API_BASE}/api/admin/search-operations?days=${days}`, { credentials: "include" }); const payload = await response.json().catch(() => ({})) as Payload & { error?: string }; if (!response.ok) return setNotice(payload.error || "搜索运营数据加载失败"); setData(payload); };
  useEffect(() => { void load(); }, [days]);
  const withStepUp = async (action: (ticket: string) => Promise<void>) => { const request = await fetch(`${API_BASE}/api/auth/request-admin-step-up`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: "{}" }); const issued = await request.json().catch(() => ({})) as { developmentCode?: string; error?: string }; if (!request.ok) return setNotice(issued.error || "无法请求二次验证"); const code = window.prompt(`请输入二次验证码${issued.developmentCode ? `（开发验证码：${issued.developmentCode}）` : ""}`); if (!code) return; const confirm = await fetch(`${API_BASE}/api/auth/confirm-admin-step-up`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ code }) }); const verified = await confirm.json().catch(() => ({})) as { ticket?: string; error?: string }; if (!confirm.ok || !verified.ticket) return setNotice(verified.error || "二次验证失败"); await action(verified.ticket); };
  const save = () => void withStepUp(async (ticket) => { const body = { kind, source, target: kind === "synonym" ? target.split(/[，,]/).map((item) => item.trim()).filter(Boolean) : kind === "zero_result" ? { message: target, productId: productId || undefined } : target, weight: Number(weight) }; const response = await fetch(`${API_BASE}/api/admin/search-operations`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json", "X-Admin-Step-Up": ticket }, body: JSON.stringify(body) }); const payload = await response.json().catch(() => ({})) as { error?: string }; if (!response.ok) return setNotice(payload.error || "规则保存失败"); setSource(""); setTarget(""); setProductId(""); setNotice("搜索规则已保存"); void load(); });
  const update = (rule: Rule, enabled: boolean) => void withStepUp(async (ticket) => { const response = await fetch(`${API_BASE}/api/admin/search-operations/${kind}/${encodeURIComponent(rule.id)}`, { method: "PUT", credentials: "include", headers: { "Content-Type": "application/json", "X-Admin-Step-Up": ticket }, body: JSON.stringify({ enabled, weight: rule.weight }) }); if (!response.ok) return setNotice("规则更新失败"); void load(); });
  const remove = (rule: Rule) => void withStepUp(async (ticket) => { if (!window.confirm(`删除“${rule.source}”规则？`)) return; const response = await fetch(`${API_BASE}/api/admin/search-operations/${kind}/${encodeURIComponent(rule.id)}`, { method: "DELETE", credentials: "include", headers: { "X-Admin-Step-Up": ticket } }); if (!response.ok) return setNotice("规则删除失败"); void load(); });
  const rules: Rule[] = kind === "synonym" ? data?.rules.synonyms || [] : kind === "correction" ? data?.rules.corrections || [] : kind === "recommendation" ? data?.rules.recommendations || [] : data?.rules.zeroResults || [];
  return <section className="studio-panel search-operations"><div className="panel-head"><h2>搜索运营</h2><div className="analytics-toolbar"><div><button className={days === 7 ? "active" : ""} onClick={() => setDays(7)}>近 7 天</button><button className={days === 30 ? "active" : ""} onClick={() => setDays(30)}>近 30 天</button></div><button className="secondary" onClick={() => void load()}>刷新</button></div></div>{notice && <p className="auth-error">{notice}</p>}{data && <><div className="coupon-operation-stats"><span>搜索次数 <b>{data.summary.searches}</b></span><span>零结果 <b>{data.summary.zeroResults}</b></span><span>零结果率 <b>{data.summary.zeroRate}%</b></span><span>纠错使用 <b>{data.summary.corrections}</b></span></div><div className="admin-operation-grid"><div><h3>配置搜索规则</h3><select value={kind} onChange={(event) => setKind(event.target.value as Kind)}><option value="synonym">同义词扩展</option><option value="correction">纠错词</option><option value="recommendation">搜索推荐</option><option value="zero_result">无结果运营</option></select><input value={source} maxLength={50} onChange={(event) => setSource(event.target.value)} placeholder="触发搜索词" /><input value={target} maxLength={kind === "zero_result" ? 200 : 100} onChange={(event) => setTarget(event.target.value)} placeholder={kind === "synonym" ? "同义词，使用逗号分隔" : kind === "correction" ? "正确搜索词" : kind === "recommendation" ? "推荐给买家的搜索词" : "无结果时的运营提示"} />{kind === "recommendation" && <input type="number" min="1" max="10000" value={weight} onChange={(event) => setWeight(event.target.value)} placeholder="推荐权重" />}{kind === "zero_result" && <input value={productId} onChange={(event) => setProductId(event.target.value)} placeholder="推荐作品 ID（可选）" />}<button className="primary" disabled={!source.trim() || !target.trim()} onClick={save}>保存规则</button></div><div><h3>规则列表</h3><div className="admin-operation-list">{rules.map((rule) => <div key={rule.id}><span><b>{rule.source}</b> → {Array.isArray(rule.target) ? rule.target.join("、") : rule.target || rule.message}{rule.productTitle && ` · 推荐：${rule.productTitle}`}{rule.weight && ` · 权重 ${rule.weight}`}</span><button className="secondary" onClick={() => update(rule, !rule.enabled)}>{rule.enabled ? "停用" : "启用"}</button><button className="danger" onClick={() => remove(rule)}>删除</button></div>)}{!rules.length && <p>暂无此类规则</p>}</div></div></div><div className="admin-analytics-grid search-term-analytics"><div className="studio-panel analytics-ranking"><div className="panel-head"><h3>高频搜索词</h3><span>搜索 / 零结果 / 纠错</span></div>{data.terms.map((item) => <p key={item.keyword}><span>{item.keyword} · {item.searches} / {item.zeroResults} / {item.corrections}</span><b>{item.searches}</b></p>)}{!data.terms.length && <p><span>暂无搜索记录</span></p>}</div><div className="studio-panel analytics-ranking"><div className="panel-head"><h3>待运营零结果词</h3><span>优先配置引导</span></div>{data.zeroTerms.map((item) => <p key={item.keyword}><span>{item.keyword}</span><b>{item.searches} 次</b></p>)}{!data.zeroTerms.length && <p><span>暂无零结果词</span></p>}</div></div></>}</section>;
}

function ActivityOperations() {
  type ActivityProduct = { id: string; productId: string; title: string; shop: string; quotaStock: number; reservedStock: number; availableStock: number; status: string; reviewNote?: string };
  type Activity = { id: string; name: string; description: string; status: "draft" | "open" | "active" | "ended"; startsAt?: string; endsAt?: string; page: { banner?: string; theme?: { accent?: string }; modules?: string[] }; applications: { id: string; shop: string; status: string; note: string; reviewNote?: string }[]; products: ActivityProduct[] };
  const [activities, setActivities] = useState<Activity[]>([]);
  const [draft, setDraft] = useState({ id: "", name: "", description: "", status: "draft" as Activity["status"], startsAt: "", endsAt: "", banner: "", accent: "#e66020", modules: "作品墙,报名说明" });
  const [notice, setNotice] = useState("");
  const load = async () => { const response = await fetch(`${API_BASE}/api/admin/activities`, { credentials: "include" }); const payload = await response.json().catch(() => ({})) as { activities?: Activity[]; error?: string }; if (!response.ok) return setNotice(payload.error || "活动加载失败"); setActivities(payload.activities || []); };
  useEffect(() => { void load(); }, []);
  const stepUp = async (action: (ticket: string) => Promise<void>) => { const requested = await fetch(`${API_BASE}/api/auth/request-admin-step-up`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: "{}" }); const issue = await requested.json().catch(() => ({})) as { developmentCode?: string; error?: string }; if (!requested.ok) return setNotice(issue.error || "无法请求二次验证"); const code = window.prompt(`请输入二次验证码${issue.developmentCode ? `（开发验证码：${issue.developmentCode}）` : ""}`); if (!code) return; const confirmed = await fetch(`${API_BASE}/api/auth/confirm-admin-step-up`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ code }) }); const verified = await confirmed.json().catch(() => ({})) as { ticket?: string; error?: string }; if (!confirmed.ok || !verified.ticket) return setNotice(verified.error || "二次验证失败"); await action(verified.ticket); };
  const save = () => void stepUp(async (ticket) => { const response = await fetch(`${API_BASE}/api/admin/activities`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json", "X-Admin-Step-Up": ticket }, body: JSON.stringify({ id: draft.id || undefined, name: draft.name, description: draft.description, status: draft.status, startsAt: draft.startsAt || undefined, endsAt: draft.endsAt || undefined, page: { banner: draft.banner || undefined, theme: { accent: draft.accent }, modules: draft.modules.split(/[，,]/).map((item) => item.trim()).filter(Boolean).slice(0, 8) } }) }); const payload = await response.json().catch(() => ({})) as { error?: string }; if (!response.ok) return setNotice(payload.error || "活动保存失败"); setNotice("活动与页面配置已保存"); setDraft({ id: "", name: "", description: "", status: "draft", startsAt: "", endsAt: "", banner: "", accent: "#e66020", modules: "作品墙,报名说明" }); void load(); });
  const reviewApplication = (activityId: string, applicationId: string, decision: "approved" | "rejected") => void stepUp(async (ticket) => { const note = decision === "rejected" ? window.prompt("驳回原因") : ""; if (decision === "rejected" && !note) return; const response = await fetch(`${API_BASE}/api/admin/activities/${encodeURIComponent(activityId)}/applications`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json", "X-Admin-Step-Up": ticket }, body: JSON.stringify({ applicationId, decision, note }) }); if (!response.ok) return setNotice("报名审核失败"); void load(); });
  const reviewProduct = (activityId: string, activityProductId: string, decision: "active" | "rejected" | "disabled") => void stepUp(async (ticket) => { const note = decision === "rejected" ? window.prompt("驳回原因") : ""; const response = await fetch(`${API_BASE}/api/admin/activities/${encodeURIComponent(activityId)}/products`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json", "X-Admin-Step-Up": ticket }, body: JSON.stringify({ activityProductId, decision, note }) }); if (!response.ok) return setNotice("活动作品处理失败"); void load(); });
  return <section className="studio-panel activity-operations"><div className="panel-head"><h2>活动运营</h2><button className="secondary" onClick={() => void load()}>刷新</button></div>{notice && <p className="auth-error">{notice}</p>}<div className="admin-operation-grid"><div><h3>{draft.id ? "编辑活动" : "创建活动"}</h3><input value={draft.name} maxLength={80} onChange={(event) => setDraft({ ...draft, name: event.target.value })} placeholder="活动名称" /><textarea value={draft.description} maxLength={500} onChange={(event) => setDraft({ ...draft, description: event.target.value })} placeholder="活动说明" /><div className="campaign-rule"><select value={draft.status} onChange={(event) => setDraft({ ...draft, status: event.target.value as Activity["status"] })}><option value="draft">草稿</option><option value="open">开放报名</option><option value="active">活动中</option><option value="ended">已结束</option></select><input type="datetime-local" value={draft.startsAt} onChange={(event) => setDraft({ ...draft, startsAt: event.target.value })} /><input type="datetime-local" value={draft.endsAt} onChange={(event) => setDraft({ ...draft, endsAt: event.target.value })} /></div><h3>活动页装修</h3><input value={draft.banner} onChange={(event) => setDraft({ ...draft, banner: event.target.value })} placeholder="横幅图片 URL" /><input value={draft.accent} onChange={(event) => setDraft({ ...draft, accent: event.target.value })} placeholder="主题色" /><input value={draft.modules} onChange={(event) => setDraft({ ...draft, modules: event.target.value })} placeholder="页面模块，逗号分隔" /><button className="primary" disabled={!draft.name} onClick={save}>保存活动</button></div><div><h3>活动与审核队列</h3><div className="admin-operation-list">{activities.map((activity) => <div key={activity.id}><span><b>{activity.name}</b><small>{activity.status} · 报名 {activity.applications.length} · 作品 {activity.products.length}</small></span><button className="secondary" onClick={() => setDraft({ id: activity.id, name: activity.name, description: activity.description, status: activity.status, startsAt: activity.startsAt?.slice(0, 16) || "", endsAt: activity.endsAt?.slice(0, 16) || "", banner: activity.page.banner || "", accent: activity.page.theme?.accent || "#e66020", modules: (activity.page.modules || []).join(",") })}>编辑</button>{activity.applications.filter((item) => item.status === "pending").map((item) => <span key={item.id}>报名：{item.shop} · {item.note}<button className="secondary" onClick={() => reviewApplication(activity.id, item.id, "approved")}>通过</button><button className="danger" onClick={() => reviewApplication(activity.id, item.id, "rejected")}>驳回</button></span>)}{activity.products.map((item) => <span key={item.id}>作品：{item.title} · 配额 {item.quotaStock} · 已占 {item.reservedStock} · {item.status}{item.status === "pending" && <><button className="secondary" onClick={() => reviewProduct(activity.id, item.id, "active")}>启用</button><button className="danger" onClick={() => reviewProduct(activity.id, item.id, "rejected")}>驳回</button></>}{item.status === "active" && <button className="secondary" onClick={() => reviewProduct(activity.id, item.id, "disabled")}>停用</button>}</span>)}</div>)}{!activities.length && <p>暂无活动</p>}</div></div></div></section>;
}

function CouponOperations() {
  type Campaign = { id: string; name: string; type: string; status: string; claimUsers: number; claimedQuantity: number; usedQuantity: number; directIssuedQuantity: number; codeTotal: number; codeIssued: number; codeRedeemed: number; codeExpired: number; claimToRedeemRate: number };
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [campaignId, setCampaignId] = useState("");
  const [userIds, setUserIds] = useState("");
  const [segment, setSegment] = useState("");
  const [quantity, setQuantity] = useState("1");
  const [codeCount, setCodeCount] = useState("20");
  const [prefix, setPrefix] = useState("HC");
  const [expiresAt, setExpiresAt] = useState("");
  const [assignedUserIds, setAssignedUserIds] = useState("");
  const [generatedCodes, setGeneratedCodes] = useState<string[]>([]);
  const [notice, setNotice] = useState("");
  const couponCampaigns = campaigns.filter((item) => item.type === "coupon");
  const selected = couponCampaigns.find((item) => item.id === campaignId);
  const load = async () => {
    const response = await fetch(`${API_BASE}/api/admin/operations`, { credentials: "include" });
    const payload = await response.json().catch(() => ({})) as { campaigns?: Campaign[] };
    if (!response.ok) return;
    const next = payload.campaigns || [];
    setCampaigns(next);
    setCampaignId((current) => current && next.some((item) => item.id === current && item.type === "coupon") ? current : next.find((item) => item.type === "coupon")?.id || "");
  };
  useEffect(() => { void load(); }, []);
  const withStepUp = async (action: (ticket: string) => Promise<void>) => {
    const requested = await fetch(`${API_BASE}/api/auth/request-admin-step-up`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: "{}" });
    const issue = await requested.json().catch(() => ({})) as { developmentCode?: string; error?: string };
    if (!requested.ok) return setNotice(issue.error || "无法请求二次验证");
    const code = window.prompt(`请输入二次验证码${issue.developmentCode ? `（开发验证码：${issue.developmentCode}）` : ""}`);
    if (!code) return;
    const confirmed = await fetch(`${API_BASE}/api/auth/confirm-admin-step-up`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ code }) });
    const verified = await confirmed.json().catch(() => ({})) as { ticket?: string; error?: string };
    if (!confirmed.ok || !verified.ticket) return setNotice(verified.error || "二次验证失败");
    await action(verified.ticket);
  };
  const parsedIds = (value: string) => Array.from(new Set(value.split(/[\s,，]+/).map((item) => item.trim()).filter(Boolean)));
  return <section className="studio-panel coupon-operations">
    <div className="panel-head"><h2>优惠券运营</h2><button className="secondary" onClick={() => void load()}>刷新</button></div>
    {notice && <p className="auth-error">{notice}</p>}
    {!couponCampaigns.length ? <p>请先创建平台券活动。</p> : <><div className="campaign-rule"><select value={campaignId} onChange={(event) => setCampaignId(event.target.value)}>{couponCampaigns.map((item) => <option value={item.id} key={item.id}>{item.name} · {item.status}</option>)}</select><button className="secondary" onClick={() => void withStepUp(async (ticket) => { const response = await fetch(`${API_BASE}/api/admin/coupons/reminders/run`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json", "X-Admin-Step-Up": ticket }, body: "{}" }); const payload = await response.json().catch(() => ({})) as { reminders?: number; error?: string }; if (!response.ok) return setNotice(payload.error || "失效提醒扫描失败"); setNotice(`已发送 ${payload.reminders || 0} 条临期提醒`); })}>扫描临期券</button></div>
      {selected && <div className="coupon-operation-stats"><span>领券用户 <b>{selected.claimUsers}</b></span><span>已发放 <b>{selected.claimedQuantity}</b></span><span>已使用 <b>{selected.usedQuantity}</b></span><span>使用转化 <b>{selected.claimToRedeemRate}%</b></span><span>券码 {selected.codeRedeemed}/{selected.codeTotal}</span><span>失效券码 {selected.codeExpired}</span></div>}
      <div className="admin-operation-grid"><div><h3>定向发券</h3><textarea value={userIds} maxLength={12000} onChange={(event) => setUserIds(event.target.value)} placeholder="买家账号 ID，使用逗号或换行分隔" /><select value={segment} onChange={(event) => setSegment(event.target.value)}><option value="">不选择人群</option><option value="all_buyers">全部买家</option><option value="new_buyers">新买家</option><option value="repeat_buyers">复购买家</option><option value="inactive_30d">30 天未活跃买家</option></select><div className="campaign-rule"><input type="number" min="1" max="20" value={quantity} onChange={(event) => setQuantity(event.target.value)} /><button className="primary" disabled={!campaignId || (!userIds.trim() && !segment)} onClick={() => void withStepUp(async (ticket) => { const response = await fetch(`${API_BASE}/api/admin/campaigns/${encodeURIComponent(campaignId)}/issue`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json", "X-Admin-Step-Up": ticket }, body: JSON.stringify({ userIds: parsedIds(userIds), segment: segment || undefined, quantity: Number(quantity) }) }); const payload = await response.json().catch(() => ({})) as { users?: number; quantity?: number; skipped?: number; error?: string }; if (!response.ok) return setNotice(payload.error || "定向发券失败"); setNotice(`已向 ${payload.users || 0} 位买家发放 ${payload.quantity || 0} 张券，跳过 ${payload.skipped || 0} 位`); setUserIds(""); void load(); })}>发放</button></div></div><div><h3>批量生成券码</h3><div className="campaign-rule"><input type="number" min="1" max="500" value={codeCount} onChange={(event) => setCodeCount(event.target.value)} placeholder="数量" /><input value={prefix} maxLength={8} onChange={(event) => setPrefix(event.target.value.toUpperCase())} placeholder="前缀" /></div><input type="date" value={expiresAt} onChange={(event) => setExpiresAt(event.target.value)} /><textarea value={assignedUserIds} maxLength={12000} onChange={(event) => setAssignedUserIds(event.target.value)} placeholder="专属买家账号 ID，可选；填写后每人生成一张" /><button className="primary" disabled={!campaignId} onClick={() => void withStepUp(async (ticket) => { const ids = parsedIds(assignedUserIds); const response = await fetch(`${API_BASE}/api/admin/campaigns/${encodeURIComponent(campaignId)}/codes`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json", "X-Admin-Step-Up": ticket }, body: JSON.stringify({ count: Number(codeCount), prefix, expiresAt: expiresAt || undefined, assignedUserIds: ids }) }); const payload = await response.json().catch(() => ({})) as { codes?: string[]; error?: string }; if (!response.ok) return setNotice(payload.error || "券码生成失败"); setGeneratedCodes(payload.codes || []); setNotice(`已生成 ${(payload.codes || []).length} 个券码`); void load(); })}>生成券码</button>{generatedCodes.length > 0 && <textarea readOnly value={generatedCodes.join("\n")} aria-label="已生成券码" />}</div></div></>}
  </section>;
}

function GovernanceDeepOperations() {
  type RuleCondition = { field: "content" | "title" | "description" | "material" | "category" | "tags"; operator: "contains" | "equals" | "not_contains"; value: string };
  type Rule = { id: string; name: string; action: "manual_review" | "reject"; priority: number; conditions: RuleCondition[]; conditionLogic: "all" | "any"; rolloutPercent: number; releaseStatus: "draft" | "active" | "paused"; version: number; hits: number; lastHitAt?: string };
  type Task = { id: string; type: "product_moderation" | "report" | "appeal"; targetId: string; status: string; priority: "low" | "normal" | "high" | "urgent"; dueAt?: string; sla: "met" | "on_track" | "warning" | "overdue"; assigneeId?: string; assignee?: string };
  type Template = { id: string; name: string; targetType: "product" | "shop" | "user"; action: string; reason: string; enabled: boolean };
  const [rules, setRules] = useState<Rule[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [admins, setAdmins] = useState<{ id: string; name: string }[]>([]);
  const [filters, setFilters] = useState({ status: "", priority: "", sla: "" });
  const [rule, setRule] = useState({ id: "", name: "", action: "manual_review" as Rule["action"], priority: "100", conditionLogic: "all" as Rule["conditionLogic"], rolloutPercent: "100", releaseStatus: "draft" as Rule["releaseStatus"], conditions: [{ field: "content" as RuleCondition["field"], operator: "contains" as RuleCondition["operator"], value: "" }] });
  const [targetId, setTargetId] = useState("");
  const [selectedTemplateId, setSelectedTemplateId] = useState("");
  const [taskNotes, setTaskNotes] = useState<Record<string, string>>({});
  const [caseDetail, setCaseDetail] = useState<{ case: { type: string; id: string; title: string; status: string }; task?: { priority: string; dueAt?: string; sla: string }; timeline: { type: string; content: string; actor: string; createdAt: string }[] } | null>(null);
  const [notice, setNotice] = useState("");
  const stepUp = async (action: (ticket: string) => Promise<void>) => {
    const request = await fetch(`${API_BASE}/api/auth/request-admin-step-up`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: "{}" });
    const issued = await request.json().catch(() => ({})) as { error?: string; developmentCode?: string };
    if (!request.ok) return setNotice(issued.error || "无法请求二次验证");
    const code = window.prompt(`请输入二次验证码${issued.developmentCode ? `（开发验证码：${issued.developmentCode}）` : ""}`);
    if (!code) return;
    const confirmation = await fetch(`${API_BASE}/api/auth/confirm-admin-step-up`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ code }) });
    const verified = await confirmation.json().catch(() => ({})) as { error?: string; ticket?: string };
    if (!confirmation.ok || !verified.ticket) return setNotice(verified.error || "二次验证失败");
    await action(verified.ticket);
  };
  const load = async () => {
    const query = new URLSearchParams(Object.entries(filters).filter(([, value]) => value));
    const [operationsResponse, tasksResponse] = await Promise.all([fetch(`${API_BASE}/api/admin/governance`, { credentials: "include" }), fetch(`${API_BASE}/api/admin/governance/tasks?${query.toString()}`, { credentials: "include" })]);
    if (operationsResponse.ok) { const payload = await operationsResponse.json() as { rules: Rule[]; templates: Template[]; admins: { id: string; name: string }[] }; setRules(payload.rules || []); setTemplates(payload.templates || []); setAdmins(payload.admins || []); }
    if (tasksResponse.ok) setTasks(((await tasksResponse.json()) as { tasks: Task[] }).tasks || []);
  };
  useEffect(() => { void load(); }, [filters.status, filters.priority, filters.sla]);
  const openCase = async (task: Task) => {
    const type = task.type === "product_moderation" ? "product" : task.type;
    const response = await fetch(`${API_BASE}/api/admin/governance/cases/${type}/${encodeURIComponent(task.targetId)}`, { credentials: "include" });
    const payload = await response.json().catch(() => ({})) as typeof caseDetail & { error?: string };
    if (!response.ok) return setNotice(payload.error || "案件加载失败");
    setCaseDetail(payload);
  };
  return <section className="studio-panel governance-operations">
    <div className="panel-head"><h2>深度治理</h2><button className="secondary" onClick={() => void load()}>刷新队列</button></div>
    {notice && <p className="auth-error">{notice}</p>}
    <div className="admin-operation-grid"><form onSubmit={(event) => { event.preventDefault(); void stepUp(async (ticket) => { const response = await fetch(`${API_BASE}/api/admin/governance/rules`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json", "X-Admin-Step-Up": ticket }, body: JSON.stringify({ ...rule, id: rule.id || undefined, priority: Number(rule.priority), rolloutPercent: Number(rule.rolloutPercent) }) }); const payload = await response.json().catch(() => ({})) as { error?: string }; if (!response.ok) return setNotice(payload.error || "规则保存失败"); setRule({ id: "", name: "", action: "manual_review", priority: "100", conditionLogic: "all", rolloutPercent: "100", releaseStatus: "draft", conditions: [{ field: "content", operator: "contains", value: "" }] }); void load(); }); }}><h3>{rule.id ? "编辑规则新版本" : "版本化审核规则"}</h3><input required value={rule.name} maxLength={80} onChange={(event) => setRule({ ...rule, name: event.target.value })} placeholder="规则名称" /><div className="campaign-rule"><select value={rule.action} onChange={(event) => setRule({ ...rule, action: event.target.value as Rule["action"] })}><option value="manual_review">转人工审核</option><option value="reject">自动驳回</option></select><input type="number" min="1" max="999" value={rule.priority} onChange={(event) => setRule({ ...rule, priority: event.target.value })} placeholder="优先级" /><input type="number" min="0" max="100" value={rule.rolloutPercent} onChange={(event) => setRule({ ...rule, rolloutPercent: event.target.value })} placeholder="灰度比例" /></div><select value={rule.conditionLogic} onChange={(event) => setRule({ ...rule, conditionLogic: event.target.value as Rule["conditionLogic"] })}><option value="all">全部条件满足</option><option value="any">任一条件满足</option></select>{rule.conditions.map((condition, index) => <div className="campaign-rule" key={index}><select value={condition.field} onChange={(event) => setRule({ ...rule, conditions: rule.conditions.map((item, itemIndex) => itemIndex === index ? { ...item, field: event.target.value as RuleCondition["field"] } : item) })}><option value="content">全内容</option><option value="title">标题</option><option value="description">描述</option><option value="material">材质</option><option value="category">分类</option><option value="tags">标签</option></select><select value={condition.operator} onChange={(event) => setRule({ ...rule, conditions: rule.conditions.map((item, itemIndex) => itemIndex === index ? { ...item, operator: event.target.value as RuleCondition["operator"] } : item) })}><option value="contains">包含</option><option value="equals">等于</option><option value="not_contains">不包含</option></select><input required value={condition.value} maxLength={80} onChange={(event) => setRule({ ...rule, conditions: rule.conditions.map((item, itemIndex) => itemIndex === index ? { ...item, value: event.target.value } : item) })} placeholder="条件值" />{rule.conditions.length > 1 && <button type="button" className="remove" onClick={() => setRule({ ...rule, conditions: rule.conditions.filter((_, itemIndex) => itemIndex !== index) })}>×</button>}</div>)}<div><button type="button" className="secondary" disabled={rule.conditions.length >= 8} onClick={() => setRule({ ...rule, conditions: [...rule.conditions, { field: "content", operator: "contains", value: "" }] })}>添加条件</button><select value={rule.releaseStatus} onChange={(event) => setRule({ ...rule, releaseStatus: event.target.value as Rule["releaseStatus"] })}><option value="draft">草稿</option><option value="active">启用</option><option value="paused">暂停</option></select><button className="primary">保存版本</button></div></form><div><h3>命中统计与模板执行</h3><div className="admin-operation-list">{rules.slice(0, 8).map((item) => <span key={item.id}><b>{item.name}</b> · v{item.version} · 优先级 {item.priority} · 灰度 {item.rolloutPercent}% · 命中 {item.hits}{item.lastHitAt ? ` · 最近 ${item.lastHitAt}` : ""}<button className="secondary" onClick={() => setRule({ id: item.id, name: item.name, action: item.action, priority: String(item.priority), conditionLogic: item.conditionLogic, rolloutPercent: String(item.rolloutPercent), releaseStatus: item.releaseStatus, conditions: item.conditions })}>编辑</button></span>)}</div><div className="campaign-rule"><select value={selectedTemplateId} onChange={(event) => setSelectedTemplateId(event.target.value)}><option value="">选择处罚模板</option>{templates.map((item) => <option key={item.id} value={item.id}>{item.name} · {item.action}</option>)}</select><input value={targetId} onChange={(event) => setTargetId(event.target.value)} placeholder="目标 ID" /><button className="danger" disabled={!selectedTemplateId || !targetId} onClick={() => void stepUp(async (ticket) => { const response = await fetch(`${API_BASE}/api/admin/enforcement/templates/${encodeURIComponent(selectedTemplateId)}/apply`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json", "X-Admin-Step-Up": ticket }, body: JSON.stringify({ targetId }) }); const payload = await response.json().catch(() => ({})) as { error?: string }; if (!response.ok) setNotice(payload.error || "模板执行失败"); else { setTargetId(""); setNotice("已套用处罚模板"); } })}>一键处罚</button></div></div></div>
    <div className="governance-task-list"><div className="panel-head"><h3>任务队列与 SLA</h3><span><select value={filters.status} onChange={(event) => setFilters({ ...filters, status: event.target.value })}><option value="">全部状态</option><option value="pending">待处理</option><option value="in_progress">处理中</option><option value="completed">已完成</option></select><select value={filters.priority} onChange={(event) => setFilters({ ...filters, priority: event.target.value })}><option value="">全部优先级</option><option value="urgent">紧急</option><option value="high">高</option><option value="normal">普通</option><option value="low">低</option></select><select value={filters.sla} onChange={(event) => setFilters({ ...filters, sla: event.target.value })}><option value="">全部 SLA</option><option value="warning">即将超时</option><option value="overdue">已超时</option></select></span></div>{tasks.map((task) => <div key={task.id}><span><b>{task.type} · {task.priority}</b><small>{task.targetId} · 截止 {task.dueAt || "未设置"} · SLA {task.sla}</small></span><select value={task.assigneeId || ""} onChange={(event) => void stepUp(async (ticket) => { await fetch(`${API_BASE}/api/admin/governance/tasks/${encodeURIComponent(task.id)}/assign`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json", "X-Admin-Step-Up": ticket }, body: JSON.stringify({ assigneeId: event.target.value || null, note: "工作台转派" }) }); void load(); })}><option value="">未分派</option>{admins.map((admin) => <option key={admin.id} value={admin.id}>{admin.name}</option>)}</select><select value={task.priority} onChange={(event) => void stepUp(async (ticket) => { await fetch(`${API_BASE}/api/admin/governance/tasks/${encodeURIComponent(task.id)}/config`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json", "X-Admin-Step-Up": ticket }, body: JSON.stringify({ priority: event.target.value }) }); void load(); })}><option value="urgent">紧急</option><option value="high">高</option><option value="normal">普通</option><option value="low">低</option></select><button className="secondary" onClick={() => void openCase(task)}>案件</button><input value={taskNotes[task.id] || ""} onChange={(event) => setTaskNotes({ ...taskNotes, [task.id]: event.target.value })} placeholder="处理备注" /><button className="secondary" disabled={!taskNotes[task.id]?.trim()} onClick={async () => { const response = await fetch(`${API_BASE}/api/admin/governance/tasks/${encodeURIComponent(task.id)}/notes`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ content: taskNotes[task.id] }) }); if (!response.ok) return setNotice("任务备注保存失败"); setTaskNotes({ ...taskNotes, [task.id]: "" }); }}>记录</button></div>)}{!tasks.length && <p>没有符合筛选条件的任务。</p>}</div>
    {caseDetail && <div className="governance-case"><div className="panel-head"><h3>{caseDetail.case.title}</h3><span>{caseDetail.case.status}{caseDetail.task ? ` · ${caseDetail.task.priority} · ${caseDetail.task.sla}` : ""}</span></div>{caseDetail.timeline.map((item, index) => <small key={`${item.createdAt}-${index}`}>{item.createdAt} · {item.actor} · {item.type} · {item.content}</small>)}</div>}
  </section>;
}

function GovernanceServiceInsights() {
  type Admin = { id: string; name: string };
  type Task = { id: string; type: string; targetId: string; status: string; priority: string; sla: string; assignee?: string; assigneeId?: string };
  type Ticket = { id: string; subject: string; buyer: string; priority: string; status: string; assignee?: string };
  type Payload = { governance: { sla: { backlog: number; unassigned: number; warning: number; overdue: number; completed: number; onTimeCompleted: number; breachedCompleted: number; averageResolutionHours: number }; rules: { id: string; name: string; version: number; rolloutPercent: number; releaseStatus: string; hits: number; autoRejected: number; approved: number; rejected: number; pending: number; reviewPassRate: number }[] }; support: { total: number; open: number; inProgress: number; resolved: number; overdue: number; warning: number; unassigned: number; averageFirstResponseHours: number; averageResolutionHours: number }; tasks: Task[]; tickets: Ticket[]; admins: Admin[] };
  const [data, setData] = useState<Payload | null>(null);
  const [selectedTasks, setSelectedTasks] = useState<string[]>([]);
  const [selectedTickets, setSelectedTickets] = useState<string[]>([]);
  const [assigneeId, setAssigneeId] = useState("");
  const [priority, setPriority] = useState("normal");
  const [ticketStatus, setTicketStatus] = useState("in_progress");
  const [notice, setNotice] = useState("");
  const load = async () => { const response = await fetch(`${API_BASE}/api/admin/operations/insights`, { credentials: "include" }); const payload = await response.json().catch(() => ({})) as Payload & { error?: string }; if (!response.ok) return setNotice(payload.error || "治理与客服洞察加载失败"); setData(payload); setSelectedTasks((ids) => ids.filter((id) => payload.tasks.some((item) => item.id === id))); setSelectedTickets((ids) => ids.filter((id) => payload.tickets.some((item) => item.id === id))); };
  useEffect(() => { void load(); }, []);
  const stepUp = async (action: (ticket: string) => Promise<void>) => { const request = await fetch(`${API_BASE}/api/auth/request-admin-step-up`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: "{}" }); const issue = await request.json().catch(() => ({})) as { developmentCode?: string; error?: string }; if (!request.ok) return setNotice(issue.error || "无法请求二次验证"); const code = window.prompt(`请输入二次验证码${issue.developmentCode ? `（开发验证码：${issue.developmentCode}）` : ""}`); if (!code) return; const confirm = await fetch(`${API_BASE}/api/auth/confirm-admin-step-up`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ code }) }); const verified = await confirm.json().catch(() => ({})) as { ticket?: string; error?: string }; if (!confirm.ok || !verified.ticket) return setNotice(verified.error || "二次验证失败"); await action(verified.ticket); };
  const bulkTasks = (action: "assign" | "priority") => void stepUp(async (ticket) => { const response = await fetch(`${API_BASE}/api/admin/governance/tasks/bulk`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json", "X-Admin-Step-Up": ticket }, body: JSON.stringify({ taskIds: selectedTasks, action, ...(action === "assign" ? { assigneeId: assigneeId || null } : {}), ...(action === "priority" ? { priority } : {}) }) }); const payload = await response.json().catch(() => ({})) as { count?: number; error?: string }; if (!response.ok) return setNotice(payload.error || "批量治理任务处理失败"); setSelectedTasks([]); setNotice(`已处理 ${payload.count || 0} 项治理任务`); void load(); });
  const bulkTickets = (action: "assign" | "status") => void stepUp(async (ticket) => { const response = await fetch(`${API_BASE}/api/admin/support/tickets/bulk`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json", "X-Admin-Step-Up": ticket }, body: JSON.stringify({ ticketIds: selectedTickets, action, ...(action === "assign" ? { assigneeId: assigneeId || null } : { status: ticketStatus }) }) }); const payload = await response.json().catch(() => ({})) as { count?: number; error?: string }; if (!response.ok) return setNotice(payload.error || "批量工单处理失败"); setSelectedTickets([]); setNotice(`已处理 ${payload.count || 0} 张工单`); void load(); });
  const toggle = (ids: string[], id: string, setIds: (value: string[]) => void) => setIds(ids.includes(id) ? ids.filter((item) => item !== id) : [...ids, id]);
  if (!data) return null;
  return <section className="studio-panel governance-service-insights"><div className="panel-head"><h2>治理与客服效能</h2><button className="secondary" onClick={() => void load()}>刷新</button></div>{notice && <p className="auth-error">{notice}</p>}<div className="coupon-operation-stats"><span>治理待办 <b>{data.governance.sla.backlog}</b></span><span>治理超时 / 预警 <b>{data.governance.sla.overdue} / {data.governance.sla.warning}</b></span><span>治理按时完成 <b>{data.governance.sla.onTimeCompleted}</b></span><span>平均治理时长 <b>{data.governance.sla.averageResolutionHours}h</b></span><span>未分派工单 <b>{data.support.unassigned}</b></span><span>工单超时 / 预警 <b>{data.support.overdue} / {data.support.warning}</b></span><span>首响 / 解决 <b>{data.support.averageFirstResponseHours}h / {data.support.averageResolutionHours}h</b></span></div><div className="admin-analytics-grid"><div className="studio-panel analytics-ranking"><div className="panel-head"><h3>规则灰度效果</h3><span>命中后的审核结果</span></div>{data.governance.rules.map((rule) => <p key={rule.id}><span>{rule.name} v{rule.version} · 灰度 {rule.rolloutPercent}% · 命中 {rule.hits} · 自动拦截 {rule.autoRejected} · 通过率 {rule.reviewPassRate}%</span><b>通过 {rule.approved} / 驳回 {rule.rejected}</b></p>)}{!data.governance.rules.length && <p><span>暂无规则命中数据</span></p>}</div><div className="studio-panel analytics-ranking"><div className="panel-head"><h3>客服工单统计</h3><span>总计 {data.support.total}</span></div><p><span>待受理</span><b>{data.support.open}</b></p><p><span>处理中</span><b>{data.support.inProgress}</b></p><p><span>已解决</span><b>{data.support.resolved}</b></p><p><span>未分派</span><b>{data.support.unassigned}</b></p></div></div><div className="governance-batch-workspace"><div><div className="panel-head"><h3>批量治理任务</h3><span>{selectedTasks.length} 项已选</span></div><div className="governance-bulk"><label><input type="checkbox" checked={data.tasks.length > 0 && data.tasks.every((item) => selectedTasks.includes(item.id))} onChange={(event) => setSelectedTasks(event.target.checked ? data.tasks.map((item) => item.id) : [])} />全选</label><select value={assigneeId} onChange={(event) => setAssigneeId(event.target.value)}><option value="">选择管理员</option>{data.admins.map((admin) => <option key={admin.id} value={admin.id}>{admin.name}</option>)}</select><button className="secondary" disabled={!selectedTasks.length || !assigneeId} onClick={() => bulkTasks("assign")}>批量分派</button><select value={priority} onChange={(event) => setPriority(event.target.value)}><option value="urgent">紧急</option><option value="high">高</option><option value="normal">普通</option><option value="low">低</option></select><button className="secondary" disabled={!selectedTasks.length} onClick={() => bulkTasks("priority")}>改优先级</button></div><div className="admin-operation-list">{data.tasks.slice(0, 30).map((task) => <div key={task.id}><label><input type="checkbox" checked={selectedTasks.includes(task.id)} onChange={() => toggle(selectedTasks, task.id, setSelectedTasks)} />{task.type}</label><span>{task.targetId} · {task.priority} · {task.sla} · {task.assignee || "未分派"}</span></div>)}</div></div><div><div className="panel-head"><h3>批量客服工单</h3><span>{selectedTickets.length} 张已选</span></div><div className="governance-bulk"><label><input type="checkbox" checked={data.tickets.length > 0 && data.tickets.every((item) => selectedTickets.includes(item.id))} onChange={(event) => setSelectedTickets(event.target.checked ? data.tickets.map((item) => item.id) : [])} />全选</label><button className="secondary" disabled={!selectedTickets.length || !assigneeId} onClick={() => bulkTickets("assign")}>批量分派</button><select value={ticketStatus} onChange={(event) => setTicketStatus(event.target.value)}><option value="in_progress">处理中</option><option value="resolved">已解决</option><option value="closed">已关闭</option></select><button className="secondary" disabled={!selectedTickets.length} onClick={() => bulkTickets("status")}>更新状态</button></div><div className="admin-operation-list">{data.tickets.slice(0, 30).map((item) => <div key={item.id}><label><input type="checkbox" checked={selectedTickets.includes(item.id)} onChange={() => toggle(selectedTickets, item.id, setSelectedTickets)} />{item.subject}</label><span>{item.buyer} · {item.priority} · {item.status} · {item.assignee || "未分派"}</span></div>)}</div></div></div></section>;
}

function AdminServiceManagement() {
  type Application = { id: string; seller: string; legalName: string; contactPhone: string; status: string; reviewNote?: string; evidence: string[]; expiresAt?: string | null; supplementDueAt?: string | null; documents?: { id: string; type: string; url: string; status: string; reviewNote?: string }[] };
  type Ticket = { id: string; subject: string; status: string; priority: string; buyer: string; assignee?: string };
  type Report = { id: string; reason: string; status: string; reporter: string; targetType: string; targetId: string };
  const [applications, setApplications] = useState<Application[]>([]);
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [reports, setReports] = useState<Report[]>([]);
  const [caseDetail, setCaseDetail] = useState<{ case: { type: string; id: string; title: string; status: string }; timeline: { type: string; content: string; actor: string; createdAt: string }[] } | null>(null);
  const [note, setNote] = useState("");
  const [notice, setNotice] = useState("");
  const load = async () => {
    const [applicationsResponse, ticketsResponse, reportsResponse] = await Promise.all([
      fetch(`${API_BASE}/api/admin/seller-verifications`, { credentials: "include" }),
      fetch(`${API_BASE}/api/admin/support/tickets`, { credentials: "include" }),
      fetch(`${API_BASE}/api/admin/reports`, { credentials: "include" }),
    ]);
    if (applicationsResponse.ok) setApplications(((await applicationsResponse.json()) as { applications: Application[] }).applications || []);
    if (ticketsResponse.ok) setTickets(((await ticketsResponse.json()) as { tickets: Ticket[] }).tickets || []);
    if (reportsResponse.ok) setReports(((await reportsResponse.json()) as { reports: Report[] }).reports || []);
  };
  useEffect(() => { void load(); }, []);
  const stepUp = async (action: (ticket: string) => Promise<void>) => {
    const request = await fetch(`${API_BASE}/api/auth/request-admin-step-up`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: "{}" });
    const issued = await request.json().catch(() => ({})) as { developmentCode?: string; error?: string };
    if (!request.ok) return setNotice(issued.error || "无法请求二次验证");
    const code = window.prompt(`请输入二次验证码${issued.developmentCode ? `（开发验证码：${issued.developmentCode}）` : ""}`);
    if (!code) return;
    const confirm = await fetch(`${API_BASE}/api/auth/confirm-admin-step-up`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ code }) });
    const verified = await confirm.json().catch(() => ({})) as { ticket?: string; error?: string };
    if (!confirm.ok || !verified.ticket) return setNotice(verified.error || "二次验证失败");
    await action(verified.ticket);
  };
  const reviewVerification = (item: Application, decision: "approved" | "rejected" | "supplement_required") => void stepUp(async (ticket) => {
    const note = decision === "approved" ? "" : window.prompt(decision === "supplement_required" ? "补件要求" : "拒绝原因");
    if (decision !== "approved" && !note?.trim()) return;
    const response = await fetch(`${API_BASE}/api/admin/seller-verifications/${encodeURIComponent(item.id)}`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json", "X-Admin-Step-Up": ticket }, body: JSON.stringify({ decision, note }) });
    const payload = await response.json().catch(() => ({})) as { error?: string };
    if (!response.ok) return setNotice(payload.error || "认证审核失败");
    void load();
  });
  return <section className="studio-panel governance-operations">
    <div className="panel-head"><h2>案件、认证与客服工单</h2><button className="secondary" onClick={() => void load()}>刷新</button></div>
    {notice && <p className="auth-error">{notice}</p>}
    <div className="admin-operation-grid"><div><h3>卖家认证审核</h3><div className="admin-operation-list">{applications.slice(0, 12).map((item) => <div key={item.id}><b>{item.seller}</b> · {item.legalName} · {item.status}{item.supplementDueAt ? ` · 补件截止 ${item.supplementDueAt}` : ""}<small>{item.reviewNote || ""}</small><div className="verification-review-documents">{item.documents?.map((document) => <a key={document.id} href={document.url} target="_blank" rel="noreferrer">{document.type} · {document.status}</a>)}{item.evidence.map((url) => <a key={url} href={url} target="_blank" rel="noreferrer">凭证</a>)}</div>{item.status === "pending" && <><button className="secondary" onClick={() => reviewVerification(item, "approved")}>通过</button><button className="secondary" onClick={() => reviewVerification(item, "supplement_required")}>要求补件</button><button className="danger" onClick={() => reviewVerification(item, "rejected")}>拒绝</button></>}</div>)}{!applications.length && <p>暂无认证申请</p>}</div></div>
      <div><h3>平台客服工单</h3><div className="admin-operation-list">{tickets.slice(0, 12).map((item) => <span key={item.id}><b>{item.subject}</b> · {item.buyer} · {item.priority} · {item.status}<button className="secondary" onClick={async () => { await fetch(`${API_BASE}/api/admin/support/tickets/${encodeURIComponent(item.id)}/status`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ status: "resolved" }) }); void load(); }}>解决</button></span>)}{!tickets.length && <p>暂无平台工单</p>}</div></div></div>
    <div className="governance-task-list"><h3>治理案件时间线</h3>{reports.slice(0, 8).map((report) => <div key={report.id}><span><b>{report.reason}</b><small>{report.reporter} · {report.status}</small></span><button className="secondary" onClick={async () => { const response = await fetch(`${API_BASE}/api/admin/governance/cases/report/${encodeURIComponent(report.id)}`, { credentials: "include" }); const payload = await response.json().catch(() => null); if (!response.ok) return setNotice("案件加载失败"); setCaseDetail(payload); }}>查看案件</button></div>)}{caseDetail && <div className="governance-case"><b>{caseDetail.case.title} · {caseDetail.case.status}</b>{caseDetail.timeline.map((item, index) => <small key={`${item.createdAt}-${index}`}>{item.createdAt} · {item.actor} · {item.content}</small>)}<textarea value={note} onChange={(event) => setNote(event.target.value)} maxLength={1000} placeholder="内部案件备注" /><button className="secondary" disabled={!note.trim()} onClick={async () => { const response = await fetch(`${API_BASE}/api/admin/governance/cases/${encodeURIComponent(caseDetail.case.type)}/${encodeURIComponent(caseDetail.case.id)}/notes`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ content: note, visibility: "internal" }) }); if (!response.ok) return setNotice("案件备注保存失败"); setNote(""); const refreshed = await fetch(`${API_BASE}/api/admin/governance/cases/${encodeURIComponent(caseDetail.case.type)}/${encodeURIComponent(caseDetail.case.id)}`, { credentials: "include" }); if (refreshed.ok) setCaseDetail(await refreshed.json()); }}>添加备注</button></div>}</div>
  </section>;
}

function SellerActivityOperations({ shopId }: { shopId: string }) {
  type Activity = { id: string; name: string; description: string; status: string; application?: { id: string; status: string; note: string; reviewNote?: string } | null; myProducts?: { id: string; productId: string; title: string; quotaStock: number; reservedStock: number; productStock: number; status: string; reviewNote?: string }[] };
  const [activities, setActivities] = useState<Activity[]>([]);
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [productIds, setProductIds] = useState<Record<string, string>>({});
  const [quotas, setQuotas] = useState<Record<string, string>>({});
  const [notice, setNotice] = useState("");
  const load = async () => { const response = await fetch(`${API_BASE}/api/seller/activities?shopId=${encodeURIComponent(shopId)}`, { credentials: "include" }); const payload = await response.json().catch(() => ({})) as { activities?: Activity[]; error?: string }; if (!response.ok) return setNotice(payload.error || "活动加载失败"); setActivities(payload.activities || []); };
  useEffect(() => { void load(); }, [shopId]);
  const apply = async (activity: Activity) => { const response = await fetch(`${API_BASE}/api/seller/activity-applications`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ activityId: activity.id, shopId, note: notes[activity.id] || "" }) }); const payload = await response.json().catch(() => ({})) as { error?: string }; if (!response.ok) return setNotice(payload.error || "报名提交失败"); setNotice("报名已提交，等待平台审核"); void load(); };
  const saveProduct = async (activity: Activity) => { const response = await fetch(`${API_BASE}/api/seller/activity-products`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ applicationId: activity.application?.id, productId: productIds[activity.id], quotaStock: Number(quotas[activity.id]) }) }); const payload = await response.json().catch(() => ({})) as { error?: string }; if (!response.ok) return setNotice(payload.error || "活动作品提交失败"); setNotice("活动作品已提交，等待平台审核"); void load(); };
  return <section className="studio-panel seller-activity-operations"><div className="panel-head"><h2>活动报名与作品配额</h2><button className="secondary" onClick={() => void load()}>刷新</button></div>{notice && <p className="auth-error">{notice}</p>}<div className="governance-task-list">{activities.map((activity) => <div key={activity.id}><span><b>{activity.name}</b><small>{activity.status} · {activity.description}</small>{activity.application && <small>报名状态：{activity.application.status}{activity.application.reviewNote ? ` · ${activity.application.reviewNote}` : ""}</small>}</span>{!activity.application && activity.status === "open" && <><input value={notes[activity.id] || ""} maxLength={500} onChange={(event) => setNotes({ ...notes, [activity.id]: event.target.value })} placeholder="报名说明" /><button className="primary" onClick={() => void apply(activity)}>报名</button></>}{activity.application?.status === "approved" && <div className="campaign-rule"><input value={productIds[activity.id] || ""} onChange={(event) => setProductIds({ ...productIds, [activity.id]: event.target.value })} placeholder="作品 ID" /><input type="number" min="0" value={quotas[activity.id] || ""} onChange={(event) => setQuotas({ ...quotas, [activity.id]: event.target.value })} placeholder="活动配额" /><button className="secondary" disabled={!productIds[activity.id] || !quotas[activity.id]} onClick={() => void saveProduct(activity)}>提交作品</button></div>}<div className="admin-operation-list">{activity.myProducts?.map((item) => <span key={item.id}>{item.title} · 配额 {item.quotaStock} · 已占 {item.reservedStock} · 作品库存 {item.productStock} · {item.status}{item.reviewNote ? ` · ${item.reviewNote}` : ""}</span>)}</div></div>)}{!activities.length && <p>暂无可报名或已报名活动</p>}</div></section>;
}

function SellerServiceManagementLegacy({ shopId }: { shopId: string }) {
  type Ticket = { id: string; subject: string; status: string; priority: string; buyer: string; messages?: { id: string; sender: string; content: string; attachmentUrl?: string; createdAt: string }[] };
  type Staff = { id: string; name: string; phone?: string; email?: string; role: "operator" | "fulfillment" | "customer_service"; status: "active" | "disabled"; permissions: string[] };
  const [verification, setVerification] = useState<{ status: string; application?: { reviewNote?: string; evidence?: string[] } | null } | null>(null);
  const [verificationDraft, setVerificationDraft] = useState({ legalName: "", identityNumber: "", contactPhone: "", evidence: [] as string[] });
  const [staff, setStaff] = useState<Staff[]>([]);
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [member, setMember] = useState({ userId: "", role: "customer_service" as Staff["role"] });
  const [ticketReply, setTicketReply] = useState<Record<string, string>>({});
  const [notice, setNotice] = useState("");
  const load = async () => {
    const [verificationResponse, staffResponse, ticketResponse] = await Promise.all([
      fetch(`${API_BASE}/api/seller/verification`, { credentials: "include" }),
      fetch(`${API_BASE}/api/seller/staff`, { credentials: "include" }),
      fetch(`${API_BASE}/api/seller/support/tickets`, { credentials: "include" }),
    ]);
    if (verificationResponse.ok) setVerification(((await verificationResponse.json()) as { verification: typeof verification }).verification);
    if (staffResponse.ok) setStaff(((await staffResponse.json()) as { staff: Staff[] }).staff || []);
    if (ticketResponse.ok) setTickets(((await ticketResponse.json()) as { tickets: Ticket[] }).tickets || []);
  };
  useEffect(() => { void load(); }, []);
  const uploadEvidence = async (file?: File) => {
    if (!file) return;
    const data = await new Promise<string>((resolve, reject) => { const reader = new FileReader(); reader.onload = () => resolve(String(reader.result)); reader.onerror = () => reject(new Error("图片读取失败")); reader.readAsDataURL(file); });
    const response = await fetch(`${API_BASE}/api/media`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ data, mediaType: "image" }) });
    const payload = await response.json().catch(() => ({})) as { url?: string; error?: string };
    if (!response.ok || !payload.url) throw new Error(payload.error || "图片上传失败");
    setVerificationDraft((value) => ({ ...value, evidence: [...value.evidence, payload.url!].slice(0, 6) }));
  };
  return <section className="studio-panel operation-settings">
    <div className="panel-head"><h2>认证、成员与客服</h2><button className="secondary" onClick={() => void load()}>刷新</button></div>
    {notice && <p className="auth-error">{notice}</p>}
    <div className="admin-operation-grid">
      <form onSubmit={async (event) => { event.preventDefault(); const response = await fetch(`${API_BASE}/api/seller/verification`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify(verificationDraft) }); const payload = await response.json().catch(() => ({})) as { error?: string }; if (!response.ok) return setNotice(payload.error || "认证提交失败"); setNotice("认证资料已提交，等待平台审核"); void load(); }}>
        <h3>卖家认证</h3><p>当前状态：{verification?.status || "loading"}{verification?.application?.reviewNote ? ` · ${verification.application.reviewNote}` : ""}</p>
        <input required value={verificationDraft.legalName} onChange={(event) => setVerificationDraft((value) => ({ ...value, legalName: event.target.value }))} placeholder="真实姓名 / 主体名称" />
        <input required value={verificationDraft.identityNumber} onChange={(event) => setVerificationDraft((value) => ({ ...value, identityNumber: event.target.value }))} placeholder="证件号码" />
        <input required value={verificationDraft.contactPhone} onChange={(event) => setVerificationDraft((value) => ({ ...value, contactPhone: event.target.value }))} placeholder="联系电话" />
        <label className="icon-upload">上传认证凭证<input type="file" accept="image/jpeg,image/png,image/webp" onChange={(event) => { const file = event.target.files?.[0]; event.currentTarget.value = ""; void uploadEvidence(file).catch((error: Error) => setNotice(error.message)); }} /></label>
        <div className="media-preview-grid">{verificationDraft.evidence.map((url) => <img key={url} src={url} alt="认证凭证" />)}</div><button className="primary">提交认证</button>
      </form>
      <div><h3>店铺成员</h3><div className="campaign-rule"><input value={member.userId} onChange={(event) => setMember({ ...member, userId: event.target.value })} placeholder="已注册账号 ID" /><select value={member.role} onChange={(event) => setMember({ ...member, role: event.target.value as Staff["role"] })}><option value="operator">运营</option><option value="fulfillment">发货</option><option value="customer_service">客服</option></select><button className="secondary" onClick={async () => { const response = await fetch(`${API_BASE}/api/seller/staff`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ shopId, ...member }) }); const payload = await response.json().catch(() => ({})) as { error?: string }; if (!response.ok) return setNotice(payload.error || "成员保存失败"); setMember({ userId: "", role: "customer_service" }); void load(); }}>添加</button></div>
        <div className="admin-operation-list">{staff.map((item) => <span key={item.id}><b>{item.name}</b> · {item.role} · {item.status}<button className="secondary" onClick={async () => { await fetch(`${API_BASE}/api/seller/staff/${encodeURIComponent(item.id)}`, { method: "PUT", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ role: item.role, status: item.status === "active" ? "disabled" : "active", permissions: item.permissions }) }); void load(); }}>{item.status === "active" ? "停用" : "启用"}</button></span>)}{!staff.length && <p>暂无成员</p>}</div>
      </div>
    </div>
    <div className="governance-task-list"><h3>客服工单</h3>{tickets.map((ticket) => <div key={ticket.id}><span><b>{ticket.subject}</b><small>{ticket.buyer} · {ticket.priority} · {ticket.status}</small></span><input value={ticketReply[ticket.id] || ""} onChange={(event) => setTicketReply((value) => ({ ...value, [ticket.id]: event.target.value }))} placeholder="回复买家" /><button className="secondary" onClick={async () => { const content = ticketReply[ticket.id]?.trim(); if (!content) return; const response = await fetch(`${API_BASE}/api/seller/support/tickets/${encodeURIComponent(ticket.id)}/messages`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ content }) }); if (!response.ok) return setNotice("工单回复失败"); setTicketReply((value) => ({ ...value, [ticket.id]: "" })); void load(); }}>回复</button><button className="primary" onClick={async () => { await fetch(`${API_BASE}/api/seller/support/tickets/${encodeURIComponent(ticket.id)}/resolve`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: "{}" }); void load(); }}>解决</button></div>)}{!tickets.length && <p>暂无店铺工单</p>}</div>
  </section>;
}

function SellerServiceManagement({ shopId }: { shopId: string }) {
  type DocumentType = "identity_front" | "identity_back" | "business_license" | "authorization" | "other";
  type VerificationDocument = { id?: string; type: DocumentType; url: string; status?: string; reviewNote?: string };
  type Verification = { status: string; legalName: string; identityNumber: string; contactPhone: string; expiresAt?: string | null; application?: { status: string; reviewNote?: string; rejectionCode?: string; supplementDueAt?: string | null; businessType?: "individual" | "enterprise"; legalRepresentative?: string; businessLicenseNo?: string; businessAddress?: string; evidence?: string[]; documents?: VerificationDocument[] } | null };
  type Staff = { id: string; name: string; role: "operator" | "fulfillment" | "customer_service"; status: "active" | "disabled"; permissions: string[] };
  type Audit = { id: string; action: string; actor: string; createdAt: string; detail: Record<string, unknown> };
  type Ticket = { id: string; subject: string; status: string; priority: string; buyer: string };
  const permissionOptions = ["products", "inventory", "orders", "shipping", "messages", "after_sales", "reviews", "settings"];
  const [verification, setVerification] = useState<Verification | null>(null);
  const [draft, setDraft] = useState({ legalName: "", identityNumber: "", contactPhone: "", businessType: "individual" as "individual" | "enterprise", legalRepresentative: "", businessLicenseNo: "", businessAddress: "", evidence: [] as string[], documents: [] as VerificationDocument[] });
  const [documentType, setDocumentType] = useState<DocumentType>("identity_front");
  const [staff, setStaff] = useState<Staff[]>([]);
  const [member, setMember] = useState({ userId: "", role: "customer_service" as Staff["role"], permissions: [] as string[] });
  const [audits, setAudits] = useState<Audit[]>([]);
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [ticketReply, setTicketReply] = useState<Record<string, string>>({});
  const [notice, setNotice] = useState("");
  const load = async () => {
    const [verificationResponse, staffResponse, auditResponse, ticketResponse] = await Promise.all([
      fetch(`${API_BASE}/api/seller/verification`, { credentials: "include" }), fetch(`${API_BASE}/api/seller/staff`, { credentials: "include" }), fetch(`${API_BASE}/api/seller/staff/audit`, { credentials: "include" }), fetch(`${API_BASE}/api/seller/support/tickets`, { credentials: "include" }),
    ]);
    if (verificationResponse.ok) {
      const next = ((await verificationResponse.json()) as { verification: Verification }).verification;
      setVerification(next);
      setDraft((value) => ({ ...value, legalName: next.legalName || value.legalName, identityNumber: next.identityNumber || value.identityNumber, contactPhone: next.contactPhone || value.contactPhone }));
    }
    if (staffResponse.ok) setStaff(((await staffResponse.json()) as { staff: Staff[] }).staff || []);
    if (auditResponse.ok) setAudits(((await auditResponse.json()) as { logs: Audit[] }).logs || []);
    if (ticketResponse.ok) setTickets(((await ticketResponse.json()) as { tickets: Ticket[] }).tickets || []);
  };
  useEffect(() => { void load(); }, []);
  const uploadDocument = async (file?: File) => {
    if (!file) return;
    const data = await new Promise<string>((resolve, reject) => { const reader = new FileReader(); reader.onload = () => resolve(String(reader.result)); reader.onerror = () => reject(new Error("图片读取失败")); reader.readAsDataURL(file); });
    const response = await fetch(`${API_BASE}/api/media`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ data, mediaType: "image" }) });
    const payload = await response.json().catch(() => ({})) as { url?: string; error?: string };
    if (!response.ok || !payload.url) throw new Error(payload.error || "图片上传失败");
    setDraft((value) => ({ ...value, evidence: [...value.evidence, payload.url!].slice(0, 6), documents: [...value.documents, { type: documentType, url: payload.url! }].slice(0, 8) }));
  };
  const togglePermission = (permissions: string[], permission: string) => permissions.includes(permission) ? permissions.filter((item) => item !== permission) : [...permissions, permission];
  const saveStaff = async (item: Staff, patch: Partial<Staff>) => {
    const response = await fetch(`${API_BASE}/api/seller/staff/${encodeURIComponent(item.id)}`, { method: "PUT", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ role: patch.role || item.role, status: patch.status || item.status, permissions: patch.permissions || item.permissions }) });
    const payload = await response.json().catch(() => ({})) as { error?: string };
    if (!response.ok) return setNotice(payload.error || "成员设置保存失败");
    void load();
  };
  const verificationStatus = verification?.status || "loading";
  const verificationStatusLabel = ({ approved: "已认证", pending: "审核中", rejected: "需补件", suspended: "已暂停", loading: "加载中" } as Record<string, string>)[verificationStatus] || "待提交";
  return <section className="studio-panel operation-settings seller-service-management">
    <div className="panel-head"><h2>认证、成员与客服</h2><button className="secondary" onClick={() => void load()}>刷新</button></div>
    {notice && <p className="auth-error">{notice}</p>}
    <div className="seller-service-grid">
      <form className="seller-service-section seller-verification-section" onSubmit={async (event) => { event.preventDefault(); const response = await fetch(`${API_BASE}/api/seller/verification`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify(draft) }); const payload = await response.json().catch(() => ({})) as { error?: string }; if (!response.ok) return setNotice(payload.error || "认证提交失败"); setNotice("认证资料已提交，等待平台审核"); setDraft((value) => ({ ...value, evidence: [], documents: [] })); void load(); }}>
        <div className="seller-service-section-head"><div><h3>卖家认证</h3><p>提交主体资料与凭证，平台审核通过后生效。</p></div><span className={`seller-service-status ${verificationStatus}`}>{verificationStatusLabel}</span></div>
        {verification?.expiresAt && <p className="seller-verification-meta">有效期至 {verification.expiresAt}</p>}
        {verification?.application?.reviewNote && <p className="auth-error">审核说明：{verification.application.reviewNote}{verification.application.supplementDueAt ? ` · 请于 ${verification.application.supplementDueAt} 前补件` : ""}</p>}
        <div className="seller-form-grid"><label><span>主体类型</span><select value={draft.businessType} onChange={(event) => setDraft((value) => ({ ...value, businessType: event.target.value as typeof value.businessType }))}><option value="individual">个人主体</option><option value="enterprise">企业主体</option></select></label><label><span>主体名称</span><input required value={draft.legalName} onChange={(event) => setDraft((value) => ({ ...value, legalName: event.target.value }))} placeholder="真实姓名 / 主体名称" /></label><label><span>证件号码</span><input required value={draft.identityNumber} onChange={(event) => setDraft((value) => ({ ...value, identityNumber: event.target.value }))} placeholder="请输入证件号码" /></label><label><span>联系电话</span><input required value={draft.contactPhone} onChange={(event) => setDraft((value) => ({ ...value, contactPhone: event.target.value }))} placeholder="请输入联系电话" /></label>{draft.businessType === "enterprise" && <><label><span>法定代表人</span><input required value={draft.legalRepresentative} onChange={(event) => setDraft((value) => ({ ...value, legalRepresentative: event.target.value }))} placeholder="请输入法定代表人" /></label><label><span>营业执照编号</span><input required value={draft.businessLicenseNo} onChange={(event) => setDraft((value) => ({ ...value, businessLicenseNo: event.target.value }))} placeholder="请输入营业执照编号" /></label><label className="seller-form-wide"><span>经营地址</span><input required value={draft.businessAddress} onChange={(event) => setDraft((value) => ({ ...value, businessAddress: event.target.value }))} placeholder="请输入经营地址" /></label></>}</div>
        <div className="seller-document-section"><div><b>认证材料</b><small>支持 JPG、PNG、WebP 格式，最多 8 张。</small></div><div className="seller-document-controls"><select value={documentType} onChange={(event) => setDocumentType(event.target.value as DocumentType)}><option value="identity_front">证件正面</option><option value="identity_back">证件反面</option><option value="business_license">营业执照</option><option value="authorization">授权书</option><option value="other">其他材料</option></select><label className="icon-upload">上传材料<input type="file" accept="image/jpeg,image/png,image/webp" onChange={(event) => { const file = event.target.files?.[0]; event.currentTarget.value = ""; void uploadDocument(file).catch((error: Error) => setNotice(error.message)); }} /></label></div><div className="media-preview-grid seller-document-previews">{draft.documents.map((item, index) => <figure key={`${item.url}-${index}`}><img src={item.url} alt={item.type} /><figcaption>{item.type}<button type="button" className="remove" onClick={() => setDraft((value) => ({ ...value, documents: value.documents.filter((_, itemIndex) => itemIndex !== index), evidence: value.evidence.filter((url) => url !== item.url) }))}>×</button></figcaption></figure>)}</div></div><div className="seller-section-actions"><button className="primary" disabled={verification?.application?.status === "pending"}>提交认证</button></div>
      </form>
      <section className="seller-service-section seller-members-section"><div className="seller-service-section-head"><div><h3>店铺成员与权限</h3><p>按岗位分配可访问的工作台功能。</p></div><span className="seller-member-count">{staff.length} 位成员</span></div><div className="seller-member-create"><input value={member.userId} onChange={(event) => setMember({ ...member, userId: event.target.value })} placeholder="已注册账号 ID" /><select value={member.role} onChange={(event) => setMember({ ...member, role: event.target.value as Staff["role"] })}><option value="operator">运营</option><option value="fulfillment">发货</option><option value="customer_service">客服</option></select><button className="secondary" type="button" onClick={async () => { const response = await fetch(`${API_BASE}/api/seller/staff`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ shopId, ...member }) }); const payload = await response.json().catch(() => ({})) as { error?: string }; if (!response.ok) return setNotice(payload.error || "成员保存失败"); setMember({ userId: "", role: "customer_service", permissions: [] }); void load(); }}>添加成员</button></div><fieldset className="seller-permission-picker"><legend>新成员权限</legend><div className="staff-permissions">{permissionOptions.map((permission) => <label key={permission}><input type="checkbox" checked={member.permissions.includes(permission)} onChange={() => setMember((value) => ({ ...value, permissions: togglePermission(value.permissions, permission) }))} />{permission}</label>)}</div></fieldset><div className="seller-member-list">{staff.map((item) => <article key={item.id} className="seller-member-item"><header><div><b>{item.name}</b><small>{item.id}</small></div><span className={`seller-member-status ${item.status}`}>{item.status === "active" ? "使用中" : "已停用"}</span></header><div className="seller-member-role"><label>岗位<select value={item.role} onChange={(event) => void saveStaff(item, { role: event.target.value as Staff["role"] })}><option value="operator">运营</option><option value="fulfillment">发货</option><option value="customer_service">客服</option></select></label></div><fieldset className="seller-permission-picker"><legend>可用权限</legend><div className="staff-permissions">{permissionOptions.map((permission) => <label key={permission}><input type="checkbox" checked={item.permissions.includes(permission)} onChange={() => void saveStaff(item, { permissions: togglePermission(item.permissions, permission) })} />{permission}</label>)}</div></fieldset><footer><button type="button" className="secondary" onClick={() => void saveStaff(item, { status: item.status === "active" ? "disabled" : "active" })}>{item.status === "active" ? "停用" : "启用"}</button><button type="button" className="danger" onClick={async () => { if (!window.confirm(`移除成员 ${item.name}？`)) return; const response = await fetch(`${API_BASE}/api/seller/staff/${encodeURIComponent(item.id)}`, { method: "DELETE", credentials: "include" }); if (!response.ok) return setNotice("成员移除失败"); void load(); }}>移除</button></footer></article>)}{!staff.length && <p className="seller-empty-state">暂无成员，可通过上方账号 ID 添加店铺协作者。</p>}</div></section>
    </div>
    <section className="seller-service-section seller-audit-section"><div className="seller-service-section-head"><div><h3>成员操作审计</h3><p>保留最近 30 条成员操作记录。</p></div></div><div className="seller-audit-list">{audits.slice(0, 30).map((item) => <article key={item.id}><div><b>{item.action}</b><small>{item.actor} · {item.createdAt}</small></div><p>{Object.entries(item.detail || {}).map(([key, value]) => `${key}: ${String(value)}`).join(" · ") || "无附加信息"}</p></article>)}{!audits.length && <p className="seller-empty-state">暂无成员操作记录</p>}</div></section>
    <section className="seller-service-section seller-tickets-section"><div className="seller-service-section-head"><div><h3>客服工单</h3><p>及时回复买家咨询，保持服务进度清晰。</p></div><span className="seller-member-count">{tickets.length} 条工单</span></div><div className="seller-ticket-list">{tickets.map((ticket) => <article key={ticket.id}><header><div><b>{ticket.subject}</b><small>{ticket.buyer} · {ticket.priority} · {ticket.status}</small></div><span className="seller-ticket-status">{ticket.status}</span></header><div className="seller-ticket-reply"><input value={ticketReply[ticket.id] || ""} onChange={(event) => setTicketReply((value) => ({ ...value, [ticket.id]: event.target.value }))} placeholder="回复买家" /><button className="secondary" onClick={async () => { const content = ticketReply[ticket.id]?.trim(); if (!content) return; const response = await fetch(`${API_BASE}/api/seller/support/tickets/${encodeURIComponent(ticket.id)}/messages`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ content }) }); if (!response.ok) return setNotice("工单回复失败"); setTicketReply((value) => ({ ...value, [ticket.id]: "" })); void load(); }}>发送回复</button></div></article>)}{!tickets.length && <p className="seller-empty-state">暂无店铺工单</p>}</div></section>
  </section>;
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
}: {
  title: string;
  text: string;
  action: string;
  onAction: () => void;
}) {
  return (
    <div className="empty">
      <ShoppingBag size={32} />
      <h2>{title}</h2>
      <p>{text}</p>
      <button className="primary" onClick={onAction}>
        {action}
      </button>
    </div>
  );
}
