import { Badge } from "@/components/ui/badge";

interface HeaderProps {
  title: string;
  description?: string;
  badge?: string | number;
  children?: React.ReactNode;
}

export function Header({ title, description, badge, children }: HeaderProps) {
  return (
    <header className="relative flex flex-col sm:flex-row sm:items-center justify-between pb-5 mb-5 animate-slide-up">
      <div>
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold tracking-tight" style={{ textWrap: "balance" }}>
            {title}
          </h1>
          {badge != null && (
            <Badge variant="info" className="text-[10px] tabular-nums">
              {badge}
            </Badge>
          )}
        </div>
        {description && (
          <p className="text-sm text-muted-foreground mt-1.5">{description}</p>
        )}
      </div>
      {children && (
        <div className="flex items-center gap-2 mt-3 sm:mt-0">{children}</div>
      )}
      {/* Accent line */}
      <div className="absolute bottom-0 left-0 right-0 h-px bg-gradient-to-r from-primary/20 via-border to-transparent" aria-hidden="true" />
    </header>
  );
}
