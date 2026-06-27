import AppLogoIcon from '@/components/app-logo-icon';

export default function AppLogo() {
    return (
        <>
            <div className="flex aspect-square size-9 items-center justify-center rounded-xl bg-sidebar-primary/90 text-sidebar-primary-foreground shadow-sm ring-1 ring-sidebar-border/60">
                <AppLogoIcon className="size-6 text-white" />
            </div>
            <div className="ml-1 grid flex-1 text-left text-sm">
                <span className="mb-0.5 truncate leading-tight font-semibold tracking-wide">
                    DRYV BOT
                </span>
            </div>
        </>
    );
}
