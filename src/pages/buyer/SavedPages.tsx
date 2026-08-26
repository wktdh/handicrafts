import { Store } from "lucide-react";
import type { ReactNode } from "react";

type Product = { id: number };
type FollowedShop = { id: string | number; name: string };

function Empty({ title, text, action, onAction }: { title: string; text: string; action: string; onAction: () => void }) {
  return <div className="empty"><h2>{title}</h2><p>{text}</p><button className="primary" onClick={onAction}>{action}</button></div>;
}

export function FavoritesPage({
  products,
  favorites,
  onOpen,
  onFavorite,
  onDiscover,
  renderProductGrid,
}: {
  products: Product[];
  favorites: number[];
  onOpen: (id: number) => void;
  onFavorite: (id: number) => void;
  onDiscover: () => void;
  renderProductGrid: (products: Product[], favorites: number[], onOpen: (id: number) => void, onFavorite: (id: number) => void) => ReactNode;
}) {
  const savedProducts = products.filter((product) =>
    favorites.includes(product.id),
  );
  return (
    <main className="container page section">
      <div className="page-title">
        <div>
          <h1>Saved items</h1>
          <p>Keep the original handmade pieces you love.</p>
        </div>
      </div>
      {savedProducts.length ? (
        renderProductGrid(savedProducts, favorites, onOpen, onFavorite)
      ) : (
        <Empty
          title="No saved items yet"
          text="Save handmade pieces from a product page to find them here later."
          action="Discover handmade"
          onAction={onDiscover}
        />
      )}
    </main>
  );
}


export function FollowingShops({
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
          <h1>Following</h1>
          <p>See the independent makers you follow.</p>
        </div>
      </div>
      {shops.length ? (
        <div className="followed-shop-list">
          {shops.map((shop) => (
            <article key={shop.id}>
              <Store size={22} />
              <b>{shop.name}</b>
              <button className="secondary" onClick={() => onUnfollow(shop)}>
                Unfollow
              </button>
            </article>
          ))}
        </div>
      ) : (
        <Empty
          title="You are not following any shops yet"
          text="Follow a maker from a product page to see them here."
          action="Discover handmade"
          onAction={onDiscover}
        />
      )}
    </div>
  );
}

