import { Link, usePage } from '@inertiajs/react';
import { ClipboardList, LayoutGrid, MapPin, Route } from 'lucide-react';
import AppLogo from '@/components/app-logo';
import { NavMain } from '@/components/nav-main';
import { NavUser } from '@/components/nav-user';
import {
    Sidebar,
    SidebarContent,
    SidebarFooter,
    SidebarHeader,
    SidebarMenu,
    SidebarMenuButton,
    SidebarMenuItem,
} from '@/components/ui/sidebar';
import { dashboard } from '@/routes';
import type { Auth, NavItem } from '@/types';

type SidebarPageProps = {
    auth: Auth;
};

const managerNavItems: NavItem[] = [
    { title: 'Tableau de bord', href: '/dashboard', icon: LayoutGrid },
    { title: 'Commissions', href: '/orders', icon: ClipboardList },
    { title: 'Plan de livraison', href: '/delivery-plan', icon: Route },
    { title: 'Salles', href: '/rooms', icon: MapPin },
];

const pharmacistNavItems: NavItem[] = [
    { title: 'Tableau de bord', href: '/dashboard', icon: LayoutGrid },
    { title: 'Mes commissions', href: '/orders', icon: ClipboardList },
];

export function AppSidebar() {
    const { auth } = usePage<SidebarPageProps>().props;
    const navItems = auth.user.role === 'manager' ? managerNavItems : pharmacistNavItems;

    return (
        <Sidebar collapsible="icon" variant="inset">
            <SidebarHeader>
                <SidebarMenu>
                    <SidebarMenuItem>
                        <SidebarMenuButton size="lg" asChild>
                            <Link href={dashboard()} prefetch>
                                <AppLogo />
                            </Link>
                        </SidebarMenuButton>
                    </SidebarMenuItem>
                </SidebarMenu>
            </SidebarHeader>

            <SidebarContent>
                <NavMain items={navItems} />
            </SidebarContent>

            <SidebarFooter>
                <NavUser />
            </SidebarFooter>
        </Sidebar>
    );
}

