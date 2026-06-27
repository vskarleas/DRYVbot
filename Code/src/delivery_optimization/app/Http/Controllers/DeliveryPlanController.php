<?php

namespace App\Http\Controllers;

use App\Models\DeliveryPlan;
use App\Models\Order;
use App\Models\Room;
use App\Services\DeliveryPlannerService;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\RedirectResponse;
use Illuminate\Http\Request;
use Inertia\Inertia;
use Inertia\Response;

class DeliveryPlanController extends Controller
{
    public function __construct(private readonly DeliveryPlannerService $planner) {}

    public function index(): Response
    {
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

        $orders = collect();

        if ($activePlan !== null && is_array($activePlan->sequence) && $activePlan->sequence !== []) {
            $orderIds = collect($activePlan->sequence)
                ->map(static fn (mixed $value): int => (int) $value)
                ->filter(static fn (int $value): bool => $value > 0)
                ->values();

            $ordersById = Order::query()
                ->whereIn('id', $orderIds)
                ->with(['departureRoom', 'arrivalRoom'])
                ->get()
                ->keyBy('id');

            $orders = $orderIds
                ->map(static fn (int $orderId): ?Order => $ordersById->get($orderId))
                ->filter()
                ->values();
        }

        $rooms = Room::where('is_active', true)->orderBy('name')->get(['id', 'name', 'code']);

        return Inertia::render('delivery-plan/index', [
            'plan' => $activePlan,
            'orders' => $orders,
            'queuedPlans' => $queuedPlans,
            'rooms' => $rooms,
        ]);
    }

    public function replan(Request $request): JsonResponse|RedirectResponse
    {
        $roomId = $request->integer('current_room_id', 0);
        $activePlan = $this->planner->getActivePlan();

        $currentRoom = $roomId
            ? Room::find($roomId)
            : ($activePlan?->currentRoom ?? $this->planner->getStartRoom());

        if ($currentRoom === null) {
            return response()->json([
                'message' => 'Impossible de replanifier sans salle courante.',
            ], 422);
        }

        $plan = $this->planner->plan($currentRoom);

        if ($request->header('X-Inertia')) {
            return back(303)->with('success', 'Plan de livraison recalculé.');
        }

        return response()->json(['plan' => $plan]);
    }
}
