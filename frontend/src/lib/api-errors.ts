function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function getValidationMessages(detail: unknown): string[] {
  if (!Array.isArray(detail)) {
    return [];
  }

  return detail
    .map((item) => {
      if (
        isRecord(item) &&
        "msg" in item &&
        typeof item.msg === "string" &&
        item.msg.trim()
      ) {
        return item.msg.trim();
      }

      return "";
    })
    .filter(Boolean);
}

function getDetailMessage(data: unknown): string {
  if (!isRecord(data) || !("detail" in data)) {
    return "";
  }

  const { detail } = data;

  if (typeof detail === "string") {
    return detail.trim();
  }

  const validationMessages = getValidationMessages(detail);
  if (validationMessages.length > 0) {
    return validationMessages.join("; ");
  }

  if (
    isRecord(detail) &&
    "msg" in detail &&
    typeof detail.msg === "string"
  ) {
    return detail.msg.trim();
  }

  return "";
}

export async function getApiErrorMessage(
  response: Response,
  fallback: string,
): Promise<string> {
  const data: unknown = await response.json().catch(() => null);
  return getDetailMessage(data) || fallback;
}
