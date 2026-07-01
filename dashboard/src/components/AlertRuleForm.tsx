// AlertRuleForm — create a new alert rule. Mirrors the backend's rule shape:
// a condition (metric + comparison + threshold), an optional tool/agent scope,
// a time window, and a delivery channel. Validation is light on the client; the
// backend rejects malformed conditions with a 422 that we surface here.
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input, Label, Select } from "@/components/ui/input";
import { useCreateAlert } from "@/hooks/useAlerts";

export function AlertRuleForm({ onDone }: { onDone: () => void }) {
  const [name, setName] = useState("");
  const [metric, setMetric] = useState("failure_rate");
  const [op, setOp] = useState(">");
  const [threshold, setThreshold] = useState("0.3");
  const [scopeType, setScopeType] = useState<"all" | "tool" | "agent">("all");
  const [scopeValue, setScopeValue] = useState("");
  const [windowMinutes, setWindowMinutes] = useState("60");
  const [channel, setChannel] = useState("log");
  const [webhookUrl, setWebhookUrl] = useState("");

  const create = useCreateAlert();

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    create.mutate(
      {
        name,
        condition: `${metric} ${op} ${threshold}`,
        scope: {
          tool: scopeType === "tool" ? scopeValue : null,
          agent: scopeType === "agent" ? scopeValue : null,
        },
        window_minutes: Number(windowMinutes),
        channel,
        webhook_url: channel === "webhook" ? webhookUrl : null,
        enabled: true,
      },
      { onSuccess: onDone },
    );
  };

  return (
    <form onSubmit={submit} className="space-y-4">
      <div className="space-y-1.5">
        <Label>Rule name</Label>
        <Input
          required
          placeholder="search tool failing"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
      </div>

      <div className="space-y-1.5">
        <Label>Condition</Label>
        <div className="grid grid-cols-3 gap-2">
          <Select value={metric} onChange={(e) => setMetric(e.target.value)}>
            <option value="failure_rate">failure_rate</option>
            <option value="error_count">error_count</option>
            <option value="total">total</option>
          </Select>
          <Select value={op} onChange={(e) => setOp(e.target.value)}>
            <option value=">">&gt;</option>
            <option value=">=">&ge;</option>
            <option value="<">&lt;</option>
            <option value="<=">&le;</option>
          </Select>
          <Input value={threshold} onChange={(e) => setThreshold(e.target.value)} />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-2">
        <div className="space-y-1.5">
          <Label>Scope</Label>
          <Select value={scopeType} onChange={(e) => setScopeType(e.target.value as typeof scopeType)}>
            <option value="all">All traffic</option>
            <option value="tool">Tool</option>
            <option value="agent">Agent</option>
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label>{scopeType === "all" ? "—" : `${scopeType} name`}</Label>
          <Input
            disabled={scopeType === "all"}
            placeholder={scopeType === "tool" ? "web_search" : "research_agent"}
            value={scopeValue}
            onChange={(e) => setScopeValue(e.target.value)}
          />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-2">
        <div className="space-y-1.5">
          <Label>Window (minutes)</Label>
          <Input
            type="number"
            min={1}
            value={windowMinutes}
            onChange={(e) => setWindowMinutes(e.target.value)}
          />
        </div>
        <div className="space-y-1.5">
          <Label>Channel</Label>
          <Select value={channel} onChange={(e) => setChannel(e.target.value)}>
            <option value="log">Log</option>
            <option value="webhook">Webhook</option>
          </Select>
        </div>
      </div>

      {channel === "webhook" && (
        <div className="space-y-1.5">
          <Label>Webhook URL</Label>
          <Input
            required
            type="url"
            placeholder="https://hooks.slack.com/..."
            value={webhookUrl}
            onChange={(e) => setWebhookUrl(e.target.value)}
          />
        </div>
      )}

      {create.isError && (
        <p className="text-xs text-danger">{(create.error as Error).message}</p>
      )}

      <div className="flex justify-end gap-2 pt-1">
        <Button type="button" variant="ghost" onClick={onDone}>
          Cancel
        </Button>
        <Button type="submit" disabled={create.isPending}>
          {create.isPending ? "Creating…" : "Create rule"}
        </Button>
      </div>
    </form>
  );
}
