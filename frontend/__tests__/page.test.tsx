import RootPage from "../app/page";

const redirect = jest.fn();

jest.mock("next/navigation", () => ({
  redirect: (href: string) => redirect(href),
}));

describe("MK1-R2 canonical root", () => {
  beforeEach(() => {
    redirect.mockClear();
  });

  it("retires the legacy Studio and redirects the root to Home", () => {
    RootPage();
    expect(redirect).toHaveBeenCalledTimes(1);
    expect(redirect).toHaveBeenCalledWith("/home");
  });
});
