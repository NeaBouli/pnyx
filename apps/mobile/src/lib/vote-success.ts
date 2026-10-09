/**
 * Actions offered after a successful vote, correction or ZK vote (MOBILE-UX-20261007-03).
 *
 * "Κλείσιμο" returns to the screen the vote was opened from (bill list, trending,
 * home, Diavgeia), with the Bills tab as fallback. "Αποτελέσματα" stays the second
 * option; ResultScreen applies the hidden-results rule itself. Android back / tap
 * outside dismisses like "Κλείσιμο". The actions only navigate, they never submit,
 * and at most one navigation happens however the dialog is closed.
 */
export interface VoteSuccessNavigation {
  canGoBack(): boolean;
  goBack(): void;
  navigate(name: string, params?: Record<string, unknown>): void;
  replace(name: string, params?: Record<string, unknown>): void;
}

export interface VoteSuccessButton {
  text: string;
  style?: "default" | "cancel" | "destructive";
  onPress: () => void;
}

export interface VoteSuccessDialog {
  buttons: VoteSuccessButton[];
  options: { cancelable: boolean; onDismiss: () => void };
}

export const CLOSE_LABEL = "Κλείσιμο";
export const RESULTS_LABEL = "Αποτελέσματα";

export function voteSuccessDialog(
  navigation: VoteSuccessNavigation,
  params: { billId: string; billTitle?: string },
): VoteSuccessDialog {
  let done = false;
  const once = (action: () => void) => () => {
    if (done) return;
    done = true;
    action();
  };
  const close = once(() => {
    if (navigation.canGoBack()) navigation.goBack();
    else navigation.navigate("Tabs", { screen: "Bills" });
  });
  const results = once(() =>
    navigation.replace("Result", { billId: params.billId, billTitle: params.billTitle, fromVote: true }),
  );
  return {
    buttons: [
      { text: CLOSE_LABEL, style: "cancel", onPress: close },
      { text: RESULTS_LABEL, onPress: results },
    ],
    options: { cancelable: true, onDismiss: close },
  };
}
