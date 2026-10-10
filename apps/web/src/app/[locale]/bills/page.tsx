import { getInitialBills } from "@/lib/initial-data";
import BillsClient from "./BillsClient";

export default async function BillsPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  // Same value the client reads via useSearchParams().get("status") || "".
  const raw = (await searchParams).status;
  const status = (Array.isArray(raw) ? raw[0] : raw) || "";
  return <BillsClient initial={await getInitialBills(status)} />;
}
