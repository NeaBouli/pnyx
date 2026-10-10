import { connection } from "next/server";
import { getInitialResults } from "@/lib/initial-data";
import ResultsClient from "./ResultsClient";

export default async function ResultsPage() {
  // Request-time render: never bake build-time API data into the HTML.
  await connection();
  return <ResultsClient initial={await getInitialResults()} />;
}
