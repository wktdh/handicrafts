import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AfterSaleForm, AuthScreen, ReviewForm, ShipmentForm } from "./App";

const order = { id: "ORDER-TEST", amount: 168 } as Parameters<typeof AfterSaleForm>[0]["order"];

describe("buyer and seller forms", () => {
  it("surfaces an authentication error returned by the API", async () => {
    const onLogin = vi.fn().mockResolvedValue("Invalid credentials");
    render(<AuthScreen onLogin={onLogin} onRegister={vi.fn()} onBack={vi.fn()} />);

    fireEvent.change(screen.getByTestId("auth-identifier"), { target: { value: "buyer@example.test" } });
    fireEvent.change(screen.getByTestId("auth-password"), { target: { value: "wrong-password" } });
    fireEvent.click(screen.getByTestId("auth-submit"));

    await waitFor(() => expect(onLogin).toHaveBeenCalledWith("buyer@example.test", "wrong-password"));
    expect(await screen.findByRole("alert")).toHaveTextContent("Invalid credentials");
  });

  it("prevents incomplete after-sale submissions and submits a valid request", async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(<AfterSaleForm order={order} onSubmit={onSubmit} onCancel={vi.fn()} />);

    expect(screen.getByTestId("after-sale-submit")).toBeDisabled();
    fireEvent.change(screen.getByTestId("after-sale-reason"), { target: { value: "Damaged in transit" } });
    expect(screen.getByTestId("after-sale-submit")).toBeEnabled();
    fireEvent.click(screen.getByTestId("after-sale-submit"));

    await waitFor(() => expect(onSubmit).toHaveBeenCalledWith(expect.objectContaining({ amount: 168, reason: "Damaged in transit", evidence: [] })));
  });

  it("requires review content before submitting a rating", async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(<ReviewForm order={order} onSubmit={onSubmit} onCancel={vi.fn()} />);

    expect(screen.getByTestId("review-submit")).toBeDisabled();
    fireEvent.change(screen.getByTestId("review-content"), { target: { value: "Excellent craftsmanship" } });
    fireEvent.click(screen.getByTestId("review-submit"));

    await waitFor(() => expect(onSubmit).toHaveBeenCalledWith({ rating: 5, content: "Excellent craftsmanship", images: [] }));
  });

  it("requires a carrier and tracking number before a seller can ship", async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(<ShipmentForm order={order} onSubmit={onSubmit} onCancel={vi.fn()} />);

    expect(screen.getByTestId("shipment-submit")).toBeDisabled();
    fireEvent.change(screen.getByTestId("shipment-carrier"), { target: { value: "Test Express" } });
    fireEvent.change(screen.getByTestId("shipment-tracking"), { target: { value: "TRACK-100" } });
    fireEvent.click(screen.getByTestId("shipment-submit"));

    await waitFor(() => expect(onSubmit).toHaveBeenCalledWith({ carrier: "Test Express", trackingNo: "TRACK-100" }));
  });

  it("rejects non-image after-sale evidence instead of submitting it", async () => {
    const { container } = render(<AfterSaleForm order={order} onSubmit={vi.fn()} onCancel={vi.fn()} />);

    const input = container.querySelector('input[type="file"]') as HTMLInputElement;
    const file = new File(["not an image"], "evidence.txt", { type: "text/plain" });
    Object.defineProperty(input, "files", { value: [file], configurable: true });
    fireEvent.change(input);

    expect(await within(container).findByRole("alert")).toBeInTheDocument();
    expect(container.querySelector(".after-sale-evidence-item")).toBeNull();
  });

  it("submits the rating selected by the buyer", async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    const { container } = render(<ReviewForm order={order} onSubmit={onSubmit} onCancel={vi.fn()} />);

    fireEvent.click(within(container).getByRole("button", { name: "2 星" }));
    fireEvent.change(within(container).getByTestId("review-content"), { target: { value: "Good details" } });
    fireEvent.click(within(container).getByTestId("review-submit"));

    await waitFor(() => expect(onSubmit).toHaveBeenCalledWith({ rating: 2, content: "Good details", images: [] }));
  });

  it("shows a registration error returned by the API", async () => {
    const onRegister = vi.fn().mockResolvedValue("Email is already registered");
    const { container } = render(<AuthScreen onLogin={vi.fn()} onRegister={onRegister} onBack={vi.fn()} />);

    fireEvent.click(within(container).getByTestId("auth-register-tab"));
    fireEvent.change(within(container).getByTestId("auth-name"), { target: { value: "New Buyer" } });
    fireEvent.change(within(container).getByTestId("auth-email"), { target: { value: "buyer@example.test" } });
    fireEvent.change(within(container).getByTestId("auth-password"), { target: { value: "password-123" } });
    fireEvent.change(within(container).getByTestId("auth-confirm-password"), { target: { value: "password-123" } });
    fireEvent.click(within(container).getByTestId("auth-submit"));

    await waitFor(() => expect(onRegister).toHaveBeenCalled());
    expect(await within(container).findByRole("alert")).toHaveTextContent("Email is already registered");
  });

  it("requires a phone number when registering as a seller", () => {
    const { container } = render(<AuthScreen onLogin={vi.fn()} onRegister={vi.fn()} onBack={vi.fn()} />);

    fireEvent.click(within(container).getByTestId("auth-register-tab"));
    const phone = within(container).getByTestId("auth-phone");
    expect(phone).not.toBeRequired();
    fireEvent.click(within(container).getAllByRole("radio")[1]);

    expect(phone).toBeRequired();
    expect(within(container).getByTestId("auth-confirm-password")).toBeInTheDocument();
  });

  it("collects and submits seller operating details on a second registration step", async () => {
    const onRegister = vi.fn().mockResolvedValue("");
    const { container } = render(<AuthScreen onLogin={vi.fn()} onRegister={onRegister} onBack={vi.fn()} />);

    fireEvent.click(within(container).getByTestId("auth-register-tab"));
    fireEvent.click(within(container).getAllByRole("radio")[1]);
    fireEvent.change(within(container).getByTestId("auth-name"), { target: { value: "Seller Test" } });
    fireEvent.change(within(container).getByTestId("auth-phone"), { target: { value: "13800138000" } });
    fireEvent.change(within(container).getByTestId("auth-phone-code"), { target: { value: "123456" } });
    fireEvent.change(within(container).getByTestId("auth-password"), { target: { value: "password-123" } });
    fireEvent.change(within(container).getByTestId("auth-confirm-password"), { target: { value: "password-123" } });
    fireEvent.click(within(container).getByTestId("auth-submit"));

    expect(within(container).getByTestId("seller-real-name")).toBeInTheDocument();
    fireEvent.change(within(container).getByTestId("seller-real-name"), { target: { value: "Seller Test" } });
    fireEvent.change(within(container).getByTestId("seller-identity-number"), { target: { value: "110101199001011234" } });
    fireEvent.change(within(container).getByTestId("seller-address"), { target: { value: "北京市朝阳区手作路 1 号" } });
    fireEvent.change(within(container).getByTestId("seller-category-select"), { target: { value: "陶艺陶瓷" } });
    fireEvent.click(within(container).getByTestId("auth-submit"));

    await waitFor(() => expect(onRegister).toHaveBeenCalledWith(
      "Seller Test", "13800138000", "", "password-123", "password-123", "123456", "seller",
      expect.objectContaining({ realName: "Seller Test", payoutProvider: "lianlian", operatingCategories: ["陶艺陶瓷"] }),
    ));
  });

  it("does not submit registration when the passwords differ", async () => {
    const onRegister = vi.fn();
    const { container } = render(<AuthScreen onLogin={vi.fn()} onRegister={onRegister} onBack={vi.fn()} />);

    fireEvent.click(within(container).getByTestId("auth-register-tab"));
    fireEvent.change(within(container).getByTestId("auth-name"), { target: { value: "New Buyer" } });
    fireEvent.change(within(container).getByTestId("auth-email"), { target: { value: "buyer@example.test" } });
    fireEvent.change(within(container).getByTestId("auth-password"), { target: { value: "password-123" } });
    fireEvent.change(within(container).getByTestId("auth-confirm-password"), { target: { value: "password-456" } });
    fireEvent.click(within(container).getByTestId("auth-submit"));

    expect(await within(container).findByRole("alert")).toHaveTextContent("两次输入的密码不一致");
    expect(onRegister).not.toHaveBeenCalled();
  });
});
