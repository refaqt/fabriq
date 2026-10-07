import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";

/** One event stream per tab. Jobs and the model refresh when the server says so. */
export function useFabriqEvents(onJob?: (job: unknown) => void) {
  const queryClient = useQueryClient();
  useEffect(() => {
    const source = new EventSource("/api/events");
    source.addEventListener("job.updated", (event) => {
      const data = JSON.parse((event as MessageEvent).data);
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
      onJob?.(data.job);
    });
    source.addEventListener("model.changed", () => {
      queryClient.invalidateQueries({ queryKey: ["model"] });
      queryClient.invalidateQueries({ queryKey: ["library"] });
    });
    source.addEventListener("git.changed", () => {
      queryClient.invalidateQueries({ queryKey: ["git"] });
    });
    return () => source.close();
  }, [queryClient, onJob]);
}
