<?php

namespace App\Http\Controllers;

use App\Enums\OrderStatus;
use App\Enums\UserRole;
use App\Models\DeliveryPlan;
use App\Models\Order;
use App\Models\Room;
use Illuminate\Http\Request;
use Inertia\Inertia;
use Inertia\Response;

class DashboardController extends Controller
{
    public function index(Request $request): Response
    {
        $user = $request->user();

        if ($user->role === UserRole::Manager) {
            return $this->managerDashboard();
        }

        return $this->pharmacistDashboard($user->id);
    }

    private function managerDashboard(): Response
    {
        $stats = [
            'pending' => Order::where('status', OrderStatus::Pending)->count(),
            'pending_critical' => Order::where('status', OrderStatus::Pending)->where('is_critical', true)->count(),
            'pending_non_critical' => Order::where('status', OrderStatus::Pending)->where('is_critical', false)->count(),
            'in_transit' => Order::where('status', OrderStatus::InTransit)->count(),
            'delivered_today' => Order::where('status', OrderStatus::Delivered)
                ->whereDate('delivered_at', today())
                ->count(),
            'cancelled_today' => Order::where('status', OrderStatus::Cancelled)
                ->whereDate('cancelled_at', today())
                ->count(),
        ];

        $activePlan = DeliveryPlan::where('status', 'active')
            ->with('currentRoom')
            ->latest()
            ->first();

        $queuedPlans = DeliveryPlan::query()
            ->where('status', 'queued')
            ->with('currentRoom')
            ->orderByDesc('is_critical')
            ->oldest('id')
            ->get();

        $recentOrders = Order::with(['departureRoom', 'arrivalRoom', 'creator'])
            ->latest()
            ->limit(10)
            ->get();

        return Inertia::render('manager/dashboard', [
            'stats' => $stats,
            'activePlan' => $activePlan,
            'queuedPlans' => $queuedPlans,
            'recentOrders' => $recentOrders,
        ]);
    }

    private function pharmacistDashboard(int $userId): Response
    {
        $stats = [
            'pending' => Order::where('created_by', $userId)->where('status', OrderStatus::Pending)->count(),
            'pending_critical' => Order::where('created_by', $userId)
                ->where('status', OrderStatus::Pending)
                ->where('is_critical', true)
                ->count(),
            'pending_non_critical' => Order::where('created_by', $userId)
                ->where('status', OrderStatus::Pending)
                ->where('is_critical', false)
                ->count(),
            'in_transit' => Order::where('created_by', $userId)->where('status', OrderStatus::InTransit)->count(),
            'delivered' => Order::where('created_by', $userId)->where('status', OrderStatus::Delivered)->count(),
            'cancelled' => Order::where('created_by', $userId)->where('status', OrderStatus::Cancelled)->count(),
        ];

        $activePlan = DeliveryPlan::query()
            ->where('status', 'active')
            ->with('currentRoom')
            ->latest('id')
            ->first();

        $queuedPlans = DeliveryPlan::query()
            ->where('status', 'queued')
            ->with('currentRoom')
            ->orderByDesc('is_critical')
            ->oldest('id')
            ->get();

        $myOrders = Order::with(['departureRoom', 'arrivalRoom'])
            ->where('created_by', $userId)
            ->latest()
            ->limit(10)
            ->get();

        $rooms = Room::where('is_active', true)->orderBy('name')->get();

        return Inertia::render('pharmacy/dashboard', [
            'stats' => $stats,
            'myOrders' => $myOrders,
            'activePlan' => $activePlan,
            'queuedPlans' => $queuedPlans,
            'rooms' => $rooms,
        ]);
    }
}
