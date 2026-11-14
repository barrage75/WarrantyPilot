import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { useJournal, useAnchorJournal } from "@/api/hooks";
import { apiErrorKey } from "@/api/errors";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
export default function Journal() {
 const { t } = useTranslation("journal"), query = useJournal(), anchor = useAnchorJournal();
 return <div className="space-y-5"><h1 className="text-3xl font-semibold">{t("title")}</h1><Card className="space-y-4">{query.isPending && <p>{t("common:loading")}</p>}{query.isError && <p role="alert">{t(apiErrorKey(query.error))}</p>}{query.data && <><h2 role="status" className={query.data.ok ? "text-xl font-semibold text-green-800" : "text-xl font-semibold text-red-800"}>{query.data.ok ? t("intact") : query.data.first_bad_seq !== null ? t("modified", { seq: query.data.first_bad_seq }) : t("invalid")}</h2><p>{t("checked", { count: query.data.checked })}</p><p>{t(query.data.anchors_ok ? "anchorsOk" : "anchorsKo")}</p></>}
 <Button disabled={anchor.isPending} onClick={() => anchor.mutate(undefined, { onSuccess: () => toast.success(t("anchored")), onError: error => toast.error(t(apiErrorKey(error))) })}>{t("anchor")}</Button>{anchor.isError && <p role="alert">{t(apiErrorKey(anchor.error))}</p>}</Card></div>;
}
