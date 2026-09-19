import { redirect } from "next/navigation";

/** O início da área logada é a lista de anúncios postados recentemente. */
export default function Page() {
  redirect("/app/results");
}
