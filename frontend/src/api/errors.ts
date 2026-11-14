import { ApiError } from "./client";
export function apiErrorKey(error: unknown) {
 if (!(error instanceof ApiError)) return "common:error";
 if (error.status === 409) return "common:conflict";
 if (error.status === 422) return "common:invalidRequest";
 if (error.status === 404) {
  const detail = JSON.stringify(error.detail);
  return detail.includes("Human approver") ? "common:unknownPerson" : "common:notFoundResource";
 }
 return "common:error";
}
