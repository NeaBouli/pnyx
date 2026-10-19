import { notFound } from "next/navigation";

// Keep unknown localized URLs inside the dynamic locale layout. Next's global
// static 404 cannot carry the proxy's fresh request nonce.
export default function UnknownPage() {
  notFound();
}
