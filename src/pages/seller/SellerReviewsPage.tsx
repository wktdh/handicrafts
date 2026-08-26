// @ts-nocheck
export default function SellerReviewsPage({ context }: { context: Record<string, any> }) {
  const {
    studioText,
    reviews,
    replyingReviewId,
    setReplyingReviewId,
    reviewReply,
    setReviewReply,
    onReplyReview,
  } = context;
  return (
    <>
            <div className="studio-title">
              <div>
                <h1>{studioText("评价管理", "Reviews")}</h1>
                <p>{studioText("查看买家反馈并回复", "Review and respond to buyer feedback")}</p>
              </div>
            </div>
            <section className="studio-panel review-manager">
              {reviews.length ? (
                reviews.map((review) => (
                  <article key={review.id}>
                    <b>
                      {"★".repeat(review.rating)}{" "}
                      <small>订单 {review.orderId}</small>
                    </b>
                    <p>{review.content}</p>
                    {!!review.images?.length && (
                      <div className="review-images">
                        {review.images.map((image) => (
                          <img key={image} src={image} alt="评价图片" />
                        ))}
                      </div>
                    )}
                    {review.followup && (
                      <p className="review-followup">追评：{review.followup}</p>
                    )}
                    {review.sellerReply ? (
                      <span>店主回复：{review.sellerReply}</span>
                    ) : replyingReviewId === review.id ? (
                      <form
                        className="seller-review-reply-form"
                        onSubmit={async (event) => {
                          event.preventDefault();
                          if (!reviewReply.trim()) return;
                          if (
                            await onReplyReview(review.id, reviewReply.trim())
                          ) {
                            setReplyingReviewId(null);
                            setReviewReply("");
                          }
                        }}
                      >
                        <textarea
                          value={reviewReply}
                          maxLength={500}
                          placeholder="回复买家的评价"
                          onChange={(event) =>
                            setReviewReply(event.target.value)
                          }
                        />
                        <div>
                          <button
                            className="secondary"
                            type="button"
                            onClick={() => {
                              setReplyingReviewId(null);
                              setReviewReply("");
                            }}
                          >
                            取消
                          </button>
                          <button
                            className="primary"
                            type="submit"
                            disabled={!reviewReply.trim()}
                          >
                            发送回复
                          </button>
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
                ))
              ) : (
                <p>暂时没有买家评价。</p>
              )}
            </section>
    </>
  );
}

