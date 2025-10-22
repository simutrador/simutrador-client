"""
Complete Trading Pipeline Orchestrator

This script orchestrates the complete trading workflow:
1. Strategy Development (Backtesting) - Develop and test strategy with historical data
2. Live Execution - Execute the strategy with live market data from simutrador-server

This is the main entry point for running the complete trading pipeline.
"""

import asyncio
import subprocess
import sys
from pathlib import Path


class TradingPipelineOrchestrator:
    """Orchestrates the complete trading pipeline."""
    
    def __init__(self):
        """Initialize the orchestrator."""
        self.project_root = Path(__file__).parent
        self.backtest_script = self.project_root / "backtest_strategy.py"
        self.live_script = self.project_root / "main.py"
        self.results = {}
    
    def print_header(self, title: str):
        """Print a formatted header."""
        print("\n" + "=" * 70)
        print(f"  {title}")
        print("=" * 70 + "\n")
    
    def print_section(self, title: str):
        """Print a formatted section."""
        print(f"\n{'─' * 70}")
        print(f"  {title}")
        print(f"{'─' * 70}\n")
    
    async def run_backtest(self) -> bool:
        """
        Run strategy backtesting with historical data.
        
        Returns:
            True if successful, False otherwise
        """
        self.print_section("PHASE 1: Strategy Backtesting")
        print("📊 Running backtest with historical data...")
        print(f"   Script: {self.backtest_script.name}\n")
        
        try:
            # Run backtest_strategy.py
            result = subprocess.run(
                [sys.executable, str(self.backtest_script)],
                cwd=str(self.project_root),
                capture_output=False,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            if result.returncode == 0:
                print("\n✅ Backtesting completed successfully!")
                self.results['backtest'] = 'SUCCESS'
                return True
            else:
                print(f"\n❌ Backtesting failed with return code: {result.returncode}")
                self.results['backtest'] = 'FAILED'
                return False
        
        except subprocess.TimeoutExpired:
            print("\n❌ Backtesting timed out (exceeded 5 minutes)")
            self.results['backtest'] = 'TIMEOUT'
            return False
        except Exception as e:
            print(f"\n❌ Error running backtest: {e}")
            self.results['backtest'] = 'ERROR'
            return False
    
    async def run_live_execution(self) -> bool:
        """
        Run live trading execution.
        
        Returns:
            True if successful, False otherwise
        """
        self.print_section("PHASE 2: Live Trading Execution")
        print("🚀 Starting live trading with real-time data...")
        print(f"   Script: {self.live_script.name}\n")
        
        try:
            # Run main.py
            result = subprocess.run(
                [sys.executable, str(self.live_script)],
                cwd=str(self.project_root),
                capture_output=False,
                text=True,
                timeout=3600  # 1 hour timeout
            )
            
            if result.returncode == 0:
                print("\n✅ Live trading session completed successfully!")
                self.results['live_execution'] = 'SUCCESS'
                return True
            else:
                print(f"\n❌ Live trading failed with return code: {result.returncode}")
                self.results['live_execution'] = 'FAILED'
                return False
        
        except subprocess.TimeoutExpired:
            print("\n❌ Live trading timed out (exceeded 1 hour)")
            self.results['live_execution'] = 'TIMEOUT'
            return False
        except Exception as e:
            print(f"\n❌ Error running live trading: {e}")
            self.results['live_execution'] = 'ERROR'
            return False
    
    async def run_pipeline(self, skip_backtest: bool = False, 
                          skip_live: bool = False) -> bool:
        """
        Run the complete trading pipeline.
        
        Args:
            skip_backtest: Skip backtesting phase
            skip_live: Skip live execution phase
        
        Returns:
            True if all phases completed successfully, False otherwise
        """
        self.print_header("🎯 TRADING PIPELINE ORCHESTRATOR")
        
        print("Pipeline Configuration:")
        print(f"  • Backtesting Phase: {'SKIPPED' if skip_backtest else 'ENABLED'}")
        print(f"  • Live Execution Phase: {'SKIPPED' if skip_live else 'ENABLED'}")
        print(f"  • Project Root: {self.project_root}\n")
        
        all_success = True
        
        # Phase 1: Backtesting
        if not skip_backtest:
            backtest_success = await self.run_backtest()
            if not backtest_success:
                print("\n⚠️  Backtesting failed. Continuing to live execution...")
                all_success = False
        else:
            print("\n⏭️  Backtesting phase skipped")
            self.results['backtest'] = 'SKIPPED'
        
        # Phase 2: Live Execution
        if not skip_live:
            live_success = await self.run_live_execution()
            if not live_success:
                all_success = False
        else:
            print("\n⏭️  Live execution phase skipped")
            self.results['live_execution'] = 'SKIPPED'
        
        # Print summary
        self.print_summary()
        
        return all_success
    
    def print_summary(self):
        """Print pipeline execution summary."""
        self.print_header("📊 PIPELINE EXECUTION SUMMARY")
        
        print("Results:")
        for phase, status in self.results.items():
            status_icon = {
                'SUCCESS': '✅',
                'FAILED': '❌',
                'ERROR': '❌',
                'TIMEOUT': '⏱️',
                'SKIPPED': '⏭️'
            }.get(status, '❓')
            
            print(f"  {status_icon} {phase.replace('_', ' ').title()}: {status}")
        
        print("\n" + "=" * 70)
        
        if all(v == 'SUCCESS' or v == 'SKIPPED' for v in self.results.values()):
            print("✅ Pipeline completed successfully!")
        else:
            print("❌ Pipeline completed with errors. Please review the output above.")
        
        print("=" * 70 + "\n")


async def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Trading Pipeline Orchestrator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_all.py                    # Run complete pipeline
  python run_all.py --skip-backtest    # Skip backtesting, run live only
  python run_all.py --skip-live        # Run backtesting only
        """
    )
    
    parser.add_argument(
        '--skip-backtest',
        action='store_true',
        help='Skip the backtesting phase'
    )
    parser.add_argument(
        '--skip-live',
        action='store_true',
        help='Skip the live execution phase'
    )
    
    args = parser.parse_args()
    
    orchestrator = TradingPipelineOrchestrator()
    success = await orchestrator.run_pipeline(
        skip_backtest=args.skip_backtest,
        skip_live=args.skip_live
    )
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())

