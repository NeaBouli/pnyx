/**
 * External deep-link routes. EVA-034: `import-account` is intentionally absent,
 * so no web page or other app can trigger an identity import; test accounts are
 * imported only from inside the app (Profile → import screen, pasted code).
 */
export const linking = {
  prefixes: ["ekklesia://", "https://ekklesia.gr"],
  config: {
    screens: {
      PolisLogin: "polis-login",
      Vote: {
        path: "el/bills/:billId",
        parse: {
          billId: (id: string) => id,
        },
      },
    },
  },
};
