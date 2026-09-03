export function getErrorMessage(error: any, fallback = "操作失败") {
  return (
    error?.response?.data?.detail ||
    error?.response?.data?.message ||
    error?.message ||
    fallback
  );
}
